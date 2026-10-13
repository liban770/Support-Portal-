from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from accounts.models import User, Department, StudentProfile, StaffProfile
from cases.models import Request, RequestCategory, RequestType, Status
from cases.permissions import visible_requests, can_process, can_decide
from core.models import SiteSettings

class PortalWorkflowSecurityTests(TestCase):
    def setUp(self):
        # Configure SiteSettings
        self.site_settings = SiteSettings.load()
        self.site_settings.max_active_requests_per_student = 2
        self.site_settings.absence_requires_document = True
        self.site_settings.block_overlapping_absence = True
        self.site_settings.save()

        # Create department
        self.dept_cs = Department.objects.create(name="Computer Science & Engineering", code="CS")
        self.dept_bus = Department.objects.create(name="Business Administration", code="BA")
        self.dept_academic = Department.objects.create(
            name="Academic Office", code="ACAD", kind=Department.Kind.ACADEMIC_OFFICE
        )

        # Create Category
        self.cat_absence = RequestCategory.objects.create(
            name="Medical & Health Excuse", request_type=RequestType.ABSENCE, default_department=self.dept_cs
        )
        self.cat_problem = RequestCategory.objects.create(
            name="Financial Dispute", request_type=RequestType.PROBLEM, default_department=self.dept_cs
        )

        # Users
        self.student_1 = User.objects.create_user(
            username="student1", email="student1@atu.edu.so", password="Password123!",
            role=User.Role.STUDENT, department=self.dept_cs, account_status=User.Status.ACTIVE, must_change_password=False
        )
        StudentProfile.objects.create(user=self.student_1, student_id="ATU2026001", program="BSc CS", year_of_study=3)

        self.student_2 = User.objects.create_user(
            username="student2", email="student2@atu.edu.so", password="Password123!",
            role=User.Role.STUDENT, department=self.dept_bus, account_status=User.Status.ACTIVE, must_change_password=False
        )
        StudentProfile.objects.create(user=self.student_2, student_id="ATU2026002", program="BBA", year_of_study=1)

        self.staff_cs = User.objects.create_user(
            username="staff1", email="staff1@atu.edu.so", password="Password123!",
            role=User.Role.STAFF, department=self.dept_cs, account_status=User.Status.ACTIVE, must_change_password=False
        )
        StaffProfile.objects.create(user=self.staff_cs, position="Academic Coordinator")

        self.dean_cs = User.objects.create_user(
            username="dean1", email="dean1@atu.edu.so", password="Password123!",
            role=User.Role.DEAN, department=self.dept_cs, account_status=User.Status.ACTIVE, must_change_password=False
        )
        self.dept_cs.head = self.dean_cs
        self.dept_cs.save()
        StaffProfile.objects.create(user=self.dean_cs, position="Dean of Engineering")

        self.academic = User.objects.create_user(
            username="academic1", email="academic1@atu.edu.so", password="Password123!",
            role=User.Role.ACADEMIC, department=self.dept_academic, account_status=User.Status.ACTIVE, must_change_password=False
        )

        self.director = User.objects.create_user(
            username="director1", email="director1@atu.edu.so", password="Password123!",
            role=User.Role.DIRECTOR, account_status=User.Status.ACTIVE, must_change_password=False
        )

        self.admin = User.objects.create_superuser(
            username="admin1", email="admin1@atu.edu.so", password="Password123!",
            role=User.Role.SUPERUSER, account_status=User.Status.ACTIVE, must_change_password=False
        )

        # Student 1 has 2 active requests in progress (hits the max limit of 2)
        self.req_absence = Request.objects.create(
            request_type=RequestType.ABSENCE,
            student=self.student_1,
            department=self.dept_cs,
            category=self.cat_absence,
            title="Medical Leave for Surgery",
            description="Requesting leave for 3 days due to dental surgery.",
            start_date=date.today() + timedelta(days=5),
            end_date=date.today() + timedelta(days=7),
            status=Status.SUBMITTED
        )

        self.req_confidential = Request.objects.create(
            request_type=RequestType.PROBLEM,
            student=self.student_1,
            department=self.dept_cs,
            category=self.cat_problem,
            title="Confidential Financial Dispute",
            description="Private financial matter.",
            is_confidential=True,
            status=Status.SUBMITTED
        )

        # Academic case
        self.req_academic_absence = Request.objects.create(
            request_type=RequestType.ABSENCE,
            student=self.student_1,
            department=self.dept_academic,
            category=self.cat_absence,
            title="Central Medical Board Leave",
            description="Escalated to Academic Office.",
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=15),
            status=Status.SUBMITTED
        )

    def test_student_scoping(self):
        """Student should only see their own requests."""
        qs = visible_requests(self.student_1)
        self.assertIn(self.req_absence, qs)
        self.assertIn(self.req_confidential, qs)

        qs2 = visible_requests(self.student_2)
        self.assertNotIn(self.req_absence, qs2)
        self.assertNotIn(self.req_confidential, qs2)

    def test_superuser_isolation_from_cases(self):
        """Superuser must not have read access to case details per system separation specification."""
        client = Client()
        client.login(username="admin1", password="Password123!")
        
        # Accessing request detail as superuser returns 404 (zero visibility)
        response = client.get(reverse('cases:detail', kwargs={'reference': self.req_absence.reference}))
        self.assertEqual(response.status_code, 404)

    def test_student_isolation_from_others(self):
        """Student 2 cannot view Student 1's request detail."""
        client = Client()
        client.login(username="student2", password="Password123!")
        response = client.get(reverse('cases:detail', kwargs={'reference': self.req_absence.reference}))
        self.assertEqual(response.status_code, 404)

    def test_dean_and_academic_permissions(self):
        """Dean can view & decide department cases; Academic can view & decide academic office cases."""
        self.assertTrue(can_process(self.dean_cs, self.req_absence))
        self.assertTrue(can_decide(self.dean_cs, self.req_absence))
        self.assertTrue(can_process(self.academic, self.req_academic_absence))
        self.assertTrue(can_decide(self.academic, self.req_academic_absence))

    def test_max_active_requests_limit(self):
        """Student with 2 active requests is blocked from submitting a 3rd request."""
        client = Client()
        client.login(username="student1", password="Password123!")
        
        # GET shows limit reached banner and disabled submit button
        get_res = client.get(reverse('cases:submit'))
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, "Active Request Limit Reached")

        # POST is rejected and redirected
        post_data = {
            'request_type': RequestType.PROBLEM,
            'category': self.cat_problem.id,
            'title': 'Another 3rd issue',
            'description': 'Should be rejected due to limit.',
            'declaration': 'on'
        }
        post_res = client.post(reverse('cases:submit'), post_data, follow=True)
        self.assertRedirects(post_res, reverse('cases:my_requests'))
        self.assertContains(post_res, "Active Request Limit Reached")

    def test_absence_requires_document(self):
        """Absence request without attachments is rejected when evidence is required."""
        client = Client()
        client.login(username="student2", password="Password123!")
        
        post_data = {
            'request_type': RequestType.ABSENCE,
            'category': self.cat_absence.id,
            'department': self.dept_cs.id,
            'reason': 'Medical illness',
            'description': 'Leave without document test.',
            'leave_type': 'absence_excuse',
            'start_date': (date.today() + timedelta(days=1)).isoformat(),
            'end_date': (date.today() + timedelta(days=2)).isoformat(),
            'declaration': 'on'
        }
        response = client.post(reverse('cases:submit'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Official supporting documentation")

    def test_overlapping_absence_dates(self):
        """Absence request covering dates overlapping with existing request is blocked."""
        # Enable 5 max requests for student1 so active cap doesn't trigger first
        self.site_settings.max_active_requests_per_student = 5
        self.site_settings.save()

        client = Client()
        client.login(username="student1", password="Password123!")
        
        dummy_file = SimpleUploadedFile("slip.pdf", b"%PDF-1.4 test slip", content_type="application/pdf")
        
        post_data = {
            'request_type': RequestType.ABSENCE,
            'category': self.cat_absence.id,
            'department': self.dept_cs.id,
            'reason': 'Overlapping leave',
            'description': 'Leave with overlapping dates.',
            'leave_type': 'absence_excuse',
            'start_date': (date.today() + timedelta(days=6)).isoformat(), # Overlaps with days 5-7
            'end_date': (date.today() + timedelta(days=8)).isoformat(),
            'attachments': dummy_file,
            'declaration': 'on'
        }
        response = client.post(reverse('cases:submit'), post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "covering overlapping dates")

    def test_escalation_to_head(self):
        """Staff can escalate case to department head without string attribute error."""
        client = Client()
        client.login(username="staff1", password="Password123!")

        url = reverse('cases:action', kwargs={'reference': self.req_absence.reference, 'action': 'escalate'})
        post_data = {
            'e-target': 'head',
            'e-note': 'Escalating to Dean Dr. Duale for policy signoff.',
        }
        res = client.post(url, post_data, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "successfully escalated to the Head of Department")
        self.req_absence.refresh_from_db()
        self.assertEqual(self.req_absence.status, Status.ESCALATED)
        self.assertEqual(self.req_absence.assigned_to, self.dean_cs)

    def test_reject_junk_and_short_input(self):
        """Students cannot submit placeholder junk, repeated characters, or too short descriptions."""
        client = Client()
        client.login(username="student2", password="Password123!")

        # 1. Junk / placeholder title and description
        post_data = {
            'request_type': RequestType.PROBLEM,
            'category': self.cat_problem.id,
            'title': 'asdf asdf',
            'description': 'test test test test',
            'declaration': 'on'
        }
        res = client.post(reverse('cases:submit'), post_data)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Placeholder or test values")

        # 2. Repeated characters (keyboard mash)
        post_data_mash = {
            'request_type': RequestType.PROBLEM,
            'category': self.cat_problem.id,
            'title': 'Need urgent assistance with fee portal',
            'description': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            'declaration': 'on'
        }
        res_mash = client.post(reverse('cases:submit'), post_data_mash)
        self.assertEqual(res_mash.status_code, 200)
        self.assertContains(res_mash, "repeated characters")

    def test_reject_unrealistic_absence_dates(self):
        """Absence requests from distant past (>45 days) are blocked."""
        client = Client()
        client.login(username="student2", password="Password123!")

        dummy_file = SimpleUploadedFile("slip.pdf", b"%PDF-1.4 test slip", content_type="application/pdf")
        post_data = {
            'request_type': RequestType.ABSENCE,
            'category': self.cat_absence.id,
            'department': self.dept_cs.id,
            'reason': 'Medical illness requiring bed rest',
            'description': 'Missed computer science algorithms lecture and lab session.',
            'leave_type': 'absence_excuse',
            'start_date': (date.today() - timedelta(days=90)).isoformat(), # 90 days ago
            'end_date': (date.today() - timedelta(days=88)).isoformat(),
            'attachments': dummy_file,
            'declaration': 'on'
        }
        res = client.post(reverse('cases:submit'), post_data)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "cannot be more than 45 days in the past")

    def test_late_class_dean_actions_and_deletion(self):
        """Department Dean can view, update status (including reject), and delete late class cases for their department."""
        cat_late = RequestCategory.objects.create(
            name="Lecture Delay / Faculty Tardiness",
            request_type=RequestType.LATE_CLASS,
            default_department=self.dept_academic
        )
        # Student submits late class for CS course
        req_late = Request.objects.create(
            request_type=RequestType.LATE_CLASS,
            student=self.student_2,
            department=self.dept_cs,
            related_department=self.dept_academic,
            category=cat_late,
            course="CS-301 Algorithms",
            title="CS-301 Algorithms – late start",
            description="Lecturer arrived 30 minutes after scheduled lecture start time.",
            class_date=date.today(),
            scheduled_start="09:00",
            actual_start="09:30",
            status=Status.SUBMITTED
        )

        client = Client()
        client.login(username="dean1", password="Password123!")

        # 1. Dean can view the late class case
        detail_res = client.get(reverse('cases:detail', kwargs={'reference': req_late.reference}))
        self.assertEqual(detail_res.status_code, 200)
        self.assertContains(detail_res, "Staff Action Console")
        self.assertContains(detail_res, "Delete Case (Head Authority)")

        # 2. Dean can reject an unsubstantiated report
        status_res = client.post(
            reverse('cases:action', kwargs={'reference': req_late.reference, 'action': 'status'}),
            {'s-status': Status.REJECTED, 's-message': 'Lecture delay investigated; timetable change was announced.'},
            follow=True
        )
        self.assertEqual(status_res.status_code, 200)
        req_late.refresh_from_db()
        self.assertEqual(req_late.status, Status.REJECTED)

        # 3. Dean can securely delete the case with typed verification
        # Wrong confirmation fails
        del_fail = client.post(
            reverse('cases:delete', kwargs={'reference': req_late.reference}),
            {'confirm_name': 'WRONG_NAME'},
            follow=True
        )
        self.assertTrue(Request.objects.filter(reference=req_late.reference).exists())

        # Exact reference succeeds
        del_ok = client.post(
            reverse('cases:delete', kwargs={'reference': req_late.reference}),
            {'confirm_name': req_late.reference},
            follow=True
        )
        self.assertFalse(Request.objects.filter(reference=req_late.reference).exists())

