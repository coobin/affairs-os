from datetime import timedelta
import re

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .department_directory import is_standard_department_code
from .ldap_directory import (
    LdapDepartmentRecord,
    LdapDirectorySyncService,
    LdapEmployeeRecord,
    LdapSnapshot,
)
from .models import (
    AdministrativeExpense,
    Asset,
    AssetCategory,
    Contract,
    Department,
    EmployeeProfile,
    ExpenseCategory,
    PurchaseRequest,
    Vehicle,
    VehicleDispatch,
)
from .serializers import DepartmentSerializer


class DepartmentNormalizationTests(TestCase):
    def setUp(self):
        self.human_resources = Department.objects.create(
            name="人力资源部",
            code="263-34",
        )
        self.administration = Department.objects.create(
            name="行政部",
            code="ADM",
        )
        self.information = Department.objects.create(
            name="信息技术部",
            code="IT",
        )
        self.existing_standard = Department.objects.create(
            name="财务部",
            code="263-99",
        )
        self.ldap_department = Department.objects.create(
            name="新 LDAP 部门",
            code="LDAP-department",
        )
        self.child = Department.objects.create(
            name="行政子部门",
            code="CHILD",
            parent=self.administration,
        )

        self.user = self._user("department-admin")
        self.other_user = self._user("department-info")
        EmployeeProfile.objects.create(
            user=self.user,
            employee_no="DEPT-001",
            department=self.administration,
        )
        EmployeeProfile.objects.create(
            user=self.other_user,
            employee_no="DEPT-002",
            department=self.information,
        )

        asset_category = AssetCategory.objects.create(
            name="测试电脑",
            code="DEPT-TEST",
        )
        Asset.objects.create(
            asset_tag="IT-DEPT-001",
            name="行政测试电脑",
            category=asset_category,
            assigned_to=self.user,
            custodian_department=self.administration,
        )
        Contract.objects.create(
            contract_no="DEPT-HT-001",
            name="信息部门测试合同",
            department=self.information,
        )
        Vehicle.objects.create(
            plate_number="湘A-DEPT1",
            name="行政测试车辆",
            department=self.administration,
        )
        VehicleDispatch.objects.create(
            request_no="DEPT-VC-001",
            requester=self.other_user,
            department=self.information,
            purpose="测试部门合并",
            destination="测试地点",
            planned_departure_at=timezone.now() + timedelta(days=1),
            planned_return_at=timezone.now() + timedelta(days=1, hours=2),
        )
        expense_category = ExpenseCategory.objects.create(
            name="部门合并测试费用",
            code="DEPT-EXP",
        )
        AdministrativeExpense.objects.create(
            occurred_on=timezone.localdate(),
            fiscal_year=timezone.localdate().year,
            category=expense_category,
            department=self.administration,
            amount="10.00",
            title="部门合并测试费用",
        )
        PurchaseRequest.objects.create(
            request_no="DEPT-PR-001",
            requester=self.other_user,
            department=self.information,
            reason="测试部门合并",
        )

    @staticmethod
    def _user(username):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(username=username)

    def test_merge_reassigns_all_department_references_and_normalizes_codes(self):
        call_command("normalize_departments")

        self.administration.refresh_from_db()
        self.information.refresh_from_db()
        self.child.refresh_from_db()
        self.assertFalse(self.administration.is_active)
        self.assertFalse(self.information.is_active)
        self.assertEqual(self.child.parent_id, self.human_resources.id)

        self.assertEqual(
            EmployeeProfile.objects.get(user=self.user).department_id,
            self.human_resources.id,
        )
        self.assertEqual(
            EmployeeProfile.objects.get(user=self.other_user).department_id,
            self.human_resources.id,
        )
        self.assertEqual(
            Asset.objects.get(asset_tag="IT-DEPT-001").custodian_department_id,
            self.human_resources.id,
        )
        self.assertEqual(
            Contract.objects.get(contract_no="DEPT-HT-001").department_id,
            self.human_resources.id,
        )
        self.assertEqual(
            Vehicle.objects.get(plate_number="湘A-DEPT1").department_id,
            self.human_resources.id,
        )
        self.assertEqual(
            VehicleDispatch.objects.get(request_no="DEPT-VC-001").department_id,
            self.human_resources.id,
        )
        self.assertEqual(
            AdministrativeExpense.objects.get(title="部门合并测试费用").department_id,
            self.human_resources.id,
        )
        self.assertEqual(
            PurchaseRequest.objects.get(request_no="DEPT-PR-001").department_id,
            self.human_resources.id,
        )

        codes = list(Department.objects.values_list("code", flat=True))
        self.assertTrue(all(re.fullmatch(r"263-[0-9]+", code) for code in codes))
        self.assertEqual(Department.objects.get(name="财务部").code, "263-99")

    def test_dry_run_does_not_change_departments(self):
        before = dict(Department.objects.values_list("id", "code"))
        active_before = dict(Department.objects.values_list("id", "is_active"))

        call_command("normalize_departments", dry_run=True)

        self.assertEqual(dict(Department.objects.values_list("id", "code")), before)
        self.assertEqual(
            dict(Department.objects.values_list("id", "is_active")),
            active_before,
        )

    def test_department_serializer_generates_code_and_rejects_merged_name(self):
        serializer = DepartmentSerializer(data={"name": "法务部", "is_active": True})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        department = serializer.save()
        self.assertTrue(is_standard_department_code(department.code))

        duplicate_alias = DepartmentSerializer(
            data={"name": "行政部", "is_active": True}
        )
        self.assertFalse(duplicate_alias.is_valid())
        self.assertIn("name", duplicate_alias.errors)


class LdapDepartmentAliasTests(TestCase):
    def test_ldap_alias_is_resolved_to_existing_human_resources_department(self):
        human_resources = Department.objects.create(
            name="人力资源部",
            code="HR",
        )
        legacy = Department.objects.create(
            name="信息技术部",
            code="IT",
            is_active=False,
        )
        user = self._user("ldap-alias-user")
        snapshot = LdapSnapshot(
            departments=(
                LdapDepartmentRecord(
                    source_id="hr-001",
                    name="人力资源部",
                    parent_source_id=None,
                    dn="cn=人力资源部,ou=groups,dc=example,dc=com",
                ),
                LdapDepartmentRecord(
                    source_id="it-001",
                    name="信息技术部",
                    parent_source_id=None,
                    dn="cn=信息技术部,ou=groups,dc=example,dc=com",
                ),
            ),
            employees=(
                LdapEmployeeRecord(
                    uid="ldap-alias-user",
                    display_name="LDAP 别名员工",
                    email="ldap-alias@example.com",
                    employee_number="LDAP-001",
                    department_source_id="it-001",
                    phone="",
                    title="",
                    active=True,
                    dn="uid=ldap-alias-user,ou=people,dc=example,dc=com",
                ),
            ),
        )

        LdapDirectorySyncService(snapshot).sync()

        human_resources.refresh_from_db()
        legacy.refresh_from_db()
        profile = EmployeeProfile.objects.get(user=user)
        self.assertEqual(profile.department_id, human_resources.id)
        self.assertFalse(legacy.is_active)
        self.assertEqual(human_resources.ldap_department_id, "hr-001")
        self.assertFalse(
            Department.objects.filter(name="信息技术部", is_active=True).exists()
        )

    @staticmethod
    def _user(username):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(username=username)

    def test_new_ldap_department_uses_standard_code(self):
        snapshot = LdapSnapshot(
            departments=(
                LdapDepartmentRecord(
                    source_id="new-001",
                    name="新建 LDAP 部门",
                    parent_source_id=None,
                    dn="cn=新建 LDAP 部门,ou=groups,dc=example,dc=com",
                ),
            ),
            employees=(
                LdapEmployeeRecord(
                    uid="new-ldap-user",
                    display_name="新建 LDAP 员工",
                    email="new-ldap@example.com",
                    employee_number="LDAP-002",
                    department_source_id="new-001",
                    phone="",
                    title="",
                    active=True,
                    dn="uid=new-ldap-user,ou=people,dc=example,dc=com",
                ),
            ),
        )

        LdapDirectorySyncService(snapshot).sync()

        department = Department.objects.get(ldap_department_id="new-001")
        self.assertTrue(is_standard_department_code(department.code))
