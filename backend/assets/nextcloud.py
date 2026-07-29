import logging
from pathlib import PurePosixPath
from urllib.parse import quote

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class NextcloudStorageError(RuntimeError):
    pass


class NextcloudStorage:
    request_headers = {"User-Agent": "AffairsOS/1.0"}

    def _check_configuration(self):
        if not settings.NEXTCLOUD_ENABLED:
            raise NextcloudStorageError("Nextcloud 文件存储尚未启用。")
        if not all(
            (
                settings.NEXTCLOUD_URL,
                settings.NEXTCLOUD_USERNAME,
                settings.NEXTCLOUD_APP_PASSWORD,
            )
        ):
            raise NextcloudStorageError("Nextcloud 文件存储配置不完整。")

    @property
    def auth(self):
        return (settings.NEXTCLOUD_USERNAME, settings.NEXTCLOUD_APP_PASSWORD)

    @property
    def timeout(self):
        return (10, settings.NEXTCLOUD_TIMEOUT)

    def _url(self, remote_path):
        self._check_configuration()
        username = quote(settings.NEXTCLOUD_USERNAME, safe="")
        parts = [quote(part, safe="") for part in PurePosixPath(remote_path).parts if part != "/"]
        suffix = "/".join(parts)
        return f"{settings.NEXTCLOUD_URL}/remote.php/dav/files/{username}/{suffix}"

    def ensure_directory(self, remote_directory):
        current = ""
        for part in PurePosixPath(remote_directory).parts:
            if part == "/":
                continue
            current = f"{current}/{part}"
            try:
                response = requests.request(
                    "MKCOL",
                    self._url(current),
                    headers=self.request_headers,
                    auth=self.auth,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                logger.exception("Nextcloud 创建目录连接失败：path=%s", current)
                raise NextcloudStorageError("Nextcloud 暂时无法连接，请稍后重试。") from exc
            status_code = response.status_code
            response.close()
            if status_code not in {201, 405}:
                logger.error(
                    "Nextcloud 创建目录失败：path=%s status=%s",
                    current,
                    status_code,
                )
                raise NextcloudStorageError("Nextcloud 目录创建失败，请稍后重试。")

    def upload(self, upload, remote_path):
        self.ensure_directory(str(PurePosixPath(remote_path).parent))
        upload.seek(0)
        try:
            response = requests.put(
                self._url(remote_path),
                data=upload,
                headers={
                    **self.request_headers,
                    "Content-Type": upload.content_type or "application/octet-stream",
                    "Content-Length": str(upload.size),
                },
                auth=self.auth,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.exception("Nextcloud 上传连接失败：path=%s", remote_path)
            raise NextcloudStorageError("Nextcloud 暂时无法连接，请稍后重试。") from exc
        status_code = response.status_code
        response.close()
        if status_code not in {201, 204}:
            logger.error(
                "Nextcloud 上传失败：path=%s status=%s",
                remote_path,
                status_code,
            )
            raise NextcloudStorageError("文件未能写入 Nextcloud，请稍后重试。")

    def download(self, remote_path):
        try:
            response = requests.get(
                self._url(remote_path),
                headers=self.request_headers,
                auth=self.auth,
                timeout=self.timeout,
                stream=True,
            )
        except requests.RequestException as exc:
            logger.exception("Nextcloud 下载连接失败：path=%s", remote_path)
            raise NextcloudStorageError("Nextcloud 暂时无法连接，请稍后重试。") from exc
        if response.status_code != 200:
            response.close()
            logger.error(
                "Nextcloud 下载失败：path=%s status=%s",
                remote_path,
                response.status_code,
            )
            raise NextcloudStorageError("文件暂时无法读取，请稍后重试。")
        return response

    def delete(self, remote_path):
        try:
            response = requests.delete(
                self._url(remote_path),
                headers=self.request_headers,
                auth=self.auth,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            logger.exception("Nextcloud 删除连接失败：path=%s", remote_path)
            raise NextcloudStorageError("Nextcloud 暂时无法连接，请稍后重试。") from exc
        status_code = response.status_code
        response.close()
        if status_code not in {204, 404}:
            logger.error(
                "Nextcloud 删除失败：path=%s status=%s",
                remote_path,
                status_code,
            )
            raise NextcloudStorageError("文件暂时无法删除，请稍后重试。")


storage = NextcloudStorage()
