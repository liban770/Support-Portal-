from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, Department, StudentProfile
from cases.models import Request, RequestType, Status
from core.models import AuditLog


class SecureDeleteTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.su = User.objects.create_user(
            username="admin_su",
            email="admin@atu.edu",
            password="Password123!",
            role=User.Role.SUPERUSER,
            account_status=User.Status.ACTIVE,
        )
        self.second_su = User.objects.create_user(
            username="second_su",
            email="second_su@atu.edu",
            password="Password123!",
            role=User.Role.SUPERUSER,
            account_status=User.Status.ACTIVE,
        )
        self.student = User.objects.create_user(
            username="std1001",
            email="std1001@atu.edu",
            password="Password123!",
            role=User.Role.STUDENT,
            account_status=User.Status.ACTIVE,
        )
        StudentProfile.objects.create(
            user=self.student,
            student_id="STD1001",
            program="Computer Science",
            year_of_study=2,
        )
        self.dept = Department.objects.create(
            name="Information Technology",
            code="IT",
        )
        self.student.department = self.dept
        self.student.save()

    def test_user_delete_requires_superuser(self):
        self.client.force_login(self.student)
        url = reverse("accounts:user_delete", kwargs={"pk": self.student.pk})
        response = self.client.post(url, {"confirm_name": "std1001"})
        # Student cannot delete accounts (redirect or 403)
        self.assertNotEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.student.pk).exists())

    def test_user_delete_blocks_self_deletion(self):
        self.client.force_login(self.su)
        url = reverse("accounts:user_delete", kwargs={"pk": self.su.pk})
        response = self.client.post(url, {"confirm_name": self.su.username})
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.assertTrue(User.objects.filter(pk=self.su.pk).exists())

    def test_user_delete_rejects_wrong_verification_name(self):
        self.client.force_login(self.su)
        url = reverse("accounts:user_delete", kwargs={"pk": self.student.pk})
        # Typo or wrong name
        response = self.client.post(url, {"confirm_name": "wrong_name"})
        self.assertRedirects(response, reverse("accounts:user_list"))
        # Student must still exist
        self.assertTrue(User.objects.filter(pk=self.student.pk).exists())

    def test_user_delete_rejects_empty_verification_name(self):
        self.client.force_login(self.su)
        url = reverse("accounts:user_delete", kwargs={"pk": self.student.pk})
        response = self.client.post(url, {"confirm_name": ""})
        self.assertRedirects(response, reverse("accounts:user_list"))
        self.assertTrue(User.objects.filter(pk=self.student.pk).exists())

    def test_user_delete_succeeds_with_exact_name_and_cleans_requests(self):
        self.client.force_login(self.su)
        # Create a request for this student to test ProtectedError handling
        req = Request.objects.create(
            student=self.student,
            department=self.dept,
            request_type=RequestType.PROBLEM,
            priority=Request.Priority.NORMAL,
            status=Status.SUBMITTED,
            title="Test subject",
            description="Test description",
        )
        url = reverse("accounts:user_delete", kwargs={"pk": self.student.pk})
        response = self.client.post(url, {"confirm_name": "std1001"})
        self.assertRedirects(response, reverse("accounts:user_list"))
        # Student should now be deleted
        self.assertFalse(User.objects.filter(pk=self.student.pk).exists())
        # Request should also be removed
        self.assertFalse(Request.objects.filter(pk=req.pk).exists())
        # AuditLog should be created
        self.assertTrue(
            AuditLog.objects.filter(action="account.deleted", details__deleted_username="std1001").exists()
        )

    def test_department_delete_rejects_wrong_verification_name(self):
        self.client.force_login(self.su)
        url = reverse("accounts:department_delete", kwargs={"pk": self.dept.pk})
        response = self.client.post(url, {"confirm_name": "Wrong Dept"})
        self.assertRedirects(response, reverse("accounts:department_detail", kwargs={"pk": self.dept.pk}))
        self.assertTrue(Department.objects.filter(pk=self.dept.pk).exists())

    def test_department_delete_succeeds_with_exact_name_and_unlinks_members(self):
        self.client.force_login(self.su)
        dept_pk = self.dept.pk
        dept_name = self.dept.name
        url = reverse("accounts:department_delete", kwargs={"pk": dept_pk})
        response = self.client.post(url, {"confirm_name": dept_name})
        self.assertRedirects(response, reverse("accounts:department_list"))
        # Department should be deleted
        self.assertFalse(Department.objects.filter(pk=dept_pk).exists())
        # Student's department should be unlinked (None)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.department)
        # Audit log should be recorded
        self.assertTrue(
            AuditLog.objects.filter(action="department.deleted", details__deleted_name=dept_name).exists()
        )

    def test_new_account_can_set_password_without_old_password(self):
        # Create a new user who must change password
        new_user = User.objects.create_user(
            username="newbie_student",
            email="newbie@atu.edu.so",
            password="TempPass123!",
            role=User.Role.STUDENT,
            account_status=User.Status.ACTIVE,
            must_change_password=True,
        )
        self.client.force_login(new_user)
        url = reverse("accounts:password_change")

        # GET request should serve the page
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context["is_first_login"])

        # POST without old_password (only new_password1 and new_password2)
        post_res = self.client.post(url, {
            "new_password1": "MySecretPass123!",
            "new_password2": "MySecretPass123!",
        })
        self.assertRedirects(post_res, reverse("core:dashboard"))

        new_user.refresh_from_db()
        self.assertFalse(new_user.must_change_password)
        self.assertTrue(new_user.check_password("MySecretPass123!"))

    def test_admin_can_set_password_in_user_edit(self):
        self.client.force_login(self.su)
        url = reverse("accounts:user_edit", kwargs={"pk": self.student.pk})
        res = self.client.post(url, {
            "first_name": "UpdatedFirst",
            "last_name": "UpdatedLast",
            "email": self.student.email,
            "username": self.student.username,
            "role": self.student.role,
            "department": self.dept.pk,
            "student_id": "STD1001",
            "password": "AdminSetPass123!",
        })
        self.assertRedirects(res, reverse("accounts:user_list"))
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password("AdminSetPass123!"))
        self.assertFalse(self.student.must_change_password)

