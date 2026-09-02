from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .ldap_directory import (
    LdapDepartmentRecord,
    LdapDirectorySyncService,
    LdapEmployeeRecord,
    LdapSnapshot,
)
from .models import Department, EmployeeProfile


User = get_user_model()


class LdapDirectorySyncTests(TestCase):
    def test_sync_links_legacy_department_and_creates_active_employee(self):
        department = Department.objects.create(name="信息技术部", code="IT")
        snapshot = LdapSnapshot(
            departments=(
                LdapDepartmentRecord(
                    source_id="dept-001",
                    name="信息技术部",
                    parent_source_id=None,
                    dn="cn=信息技术部,ou=groups,dc=example,dc=com",
                ),
            ),
            employees=(
                LdapEmployeeRecord(
                    uid="shendunbin",
                    display_name="沈敦彬",
                    email="shendunbin@example.com",
                    employee_number="260657",
                    department_source_id="dept-001",
                    phone="13800000000",
                    title="工程师",
                    active=True,
                    dn="uid=shendunbin,ou=people,dc=example,dc=com",
                ),
            ),
        )

        result = LdapDirectorySyncService(snapshot).sync()

        department.refresh_from_db()
        user = User.objects.get(username="shendunbin")
        profile = EmployeeProfile.objects.get(user=user)
        self.assertEqual(result.departments_created, 0)
        self.assertEqual(result.departments_updated, 1)
        self.assertEqual(result.employees_created, 1)
        self.assertEqual(user.first_name, "沈敦彬")
        self.assertTrue(user.is_active)
        self.assertEqual(profile.employee_no, "260657")
        self.assertEqual(profile.ldap_uid, "shendunbin")
        self.assertEqual(profile.department, department)
        self.assertEqual(department.ldap_department_id, "dept-001")

    @override_settings(LDAP_SYNC_CREATE_INACTIVE_USERS=False)
    def test_inactive_employee_is_not_created_but_existing_employee_is_deactivated(self):
        user = User.objects.create_user("lisi", first_name="李四")
        profile = EmployeeProfile.objects.create(user=user, employee_no="lisi")
        snapshot = LdapSnapshot(
            employees=(
                LdapEmployeeRecord(
                    uid="lisi",
                    display_name="李四",
                    email="",
                    employee_number="1001",
                    department_source_id=None,
                    phone="",
                    title="",
                    active=False,
                    dn="uid=lisi,ou=people,dc=example,dc=com",
                ),
                LdapEmployeeRecord(
                    uid="wangwu",
                    display_name="王五",
                    email="",
                    employee_number="1002",
                    department_source_id=None,
                    phone="",
                    title="",
                    active=False,
                    dn="uid=wangwu,ou=people,dc=example,dc=com",
                ),
            ),
        )

        result = LdapDirectorySyncService(snapshot).sync()

        user.refresh_from_db()
        profile.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(profile.ldap_uid, "lisi")
        self.assertFalse(User.objects.filter(username="wangwu").exists())
        self.assertEqual(result.employees_skipped, 1)
        self.assertEqual(result.employees_deactivated, 1)

    def test_active_employee_wins_when_historical_uid_shares_local_email(self):
        user = User.objects.create_user(
            "liufeng",
            first_name="刘峰",
            email="liufeng@example.com",
        )
        EmployeeProfile.objects.create(user=user, employee_no="liufeng")
        snapshot = LdapSnapshot(
            employees=(
                LdapEmployeeRecord(
                    uid="liufeng-90130",
                    display_name="刘峰",
                    email="liufeng@example.com",
                    employee_number="90130",
                    department_source_id=None,
                    phone="",
                    title="",
                    active=False,
                    dn="uid=liufeng-90130,ou=people,dc=example,dc=com",
                ),
                LdapEmployeeRecord(
                    uid="liufeng",
                    display_name="刘峰",
                    email="liufeng@example.com",
                    employee_number="240486",
                    department_source_id=None,
                    phone="",
                    title="",
                    active=True,
                    dn="uid=liufeng,ou=people,dc=example,dc=com",
                ),
            ),
        )

        result = LdapDirectorySyncService(snapshot).sync()

        user.refresh_from_db()
        profile = EmployeeProfile.objects.get(user=user)
        self.assertTrue(user.is_active)
        self.assertEqual(profile.ldap_uid, "liufeng")
        self.assertEqual(profile.employee_no, "240486")
        self.assertEqual(result.employees_created, 0)
        self.assertEqual(result.employees_skipped, 1)
