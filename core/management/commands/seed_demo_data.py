import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.files.base import ContentFile

from accounts.models import Department, StaffProfile, StudentProfile, User
from cases.models import (
    Attachment,
    Request,
    RequestAssignment,
    RequestCategory,
    RequestComment,
    RequestType,
    Status,
)
from core.models import AuditLog, Notification, SiteSettings


class Command(BaseCommand):
    help = "Seed comprehensive demo data matching the ATU Stitch portal design specifications."

    def handle(self, *args, **options):
        self.stdout.write("Seeding ATU Student Support Portal data...")

        # 1. System Settings
        site = SiteSettings.load()
        site.portal_name = "ATU Support Portal"
        site.current_term = "Spring 2026"
        site.support_email = "info@abaarsotechuniversity.org"
        site.support_hours = "Sun – Thu: 08:00 AM – 04:30 PM"
        site.support_location = "Building A, Academic Services Wing, Room 104"
        site.sla_days_absence = 2
        site.sla_days_problem = 5
        site.sla_days_late_class = 3
        site.max_upload_mb = 10
        site.staff_can_decide_absence = False
        site.director_can_view_confidential = True
        site.save()

        # 2. Departments
        cse, _ = Department.objects.get_or_create(
            code="CSE",
            defaults={
                "name": "Computing & Software Engineering",
                "kind": Department.Kind.ACADEMIC,
                "location": "Main Academic Quad, Building B, Room 204",
                "contact_email": "cse.support@atu.edu.so",
                "description": "Faculty of Computing & Information Technology",
            },
        )
        ete, _ = Department.objects.get_or_create(
            code="ETE",
            defaults={
                "name": "Electrical & Telecommunication",
                "kind": Department.Kind.ACADEMIC,
                "location": "Engineering Lab 4, East Wing",
                "contact_email": "ete.support@atu.edu.so",
                "description": "School of Engineering & Applied Technology",
            },
        )
        nas, _ = Department.objects.get_or_create(
            code="NAS",
            defaults={
                "name": "Natural & Applied Sciences",
                "kind": Department.Kind.ACADEMIC,
                "location": "Science Amphitheater Wing",
                "contact_email": "nas@atu.edu.so",
                "description": "Physics, Mathematics and Chemistry Division",
            },
        )
        acad, _ = Department.objects.get_or_create(
            code="ACAD",
            defaults={
                "name": "Academic Affairs Office",
                "kind": Department.Kind.ACADEMIC_OFFICE,
                "location": "Admin Building A, Registrar Hall 102",
                "contact_email": "registrar@atu.edu.so",
                "description": "Central Timetable & Academic Registry",
            },
        )
        sa_dept, _ = Department.objects.get_or_create(
            code="DIR",
            defaults={
                "name": "Student Affairs Directorate",
                "kind": Department.Kind.STUDENT_AFFAIRS,
                "location": "Student Activity Center, Room 12",
                "contact_email": "student.affairs@atu.edu.so",
                "description": "Student Welfare, Housing & Extra-Curricular Inquiries",
            },
        )
        campus_ops, _ = Department.objects.get_or_create(
            code="CIT",
            defaults={
                "name": "Campus & IT Operations",
                "kind": Department.Kind.SERVICE,
                "location": "Hardware Operations Center, Room 104",
                "contact_email": "it.support@atu.edu.so",
                "description": "Lab hardware, campus networks and facilities support",
            },
        )

        # 3. Request Categories
        # Absence
        cat_med, _ = RequestCategory.objects.get_or_create(
            name="Medical & Health Excuse",
            request_type=RequestType.ABSENCE,
            defaults={"default_department": cse, "description": "Hospital admissions, illnesses, doctor consultations"},
        )
        cat_leave, _ = RequestCategory.objects.get_or_create(
            name="Official Academic / Emergency Leave",
            request_type=RequestType.ABSENCE,
            defaults={"default_department": sa_dept, "description": "Athletic, family emergency or conference leave"},
        )

        # Problems
        cat_lab, _ = RequestCategory.objects.get_or_create(
            name="Lab & Hardware Facilities",
            request_type=RequestType.PROBLEM,
            defaults={"default_department": campus_ops, "description": "Workstation faults, projectors, network ports"},
        )
        cat_grading, _ = RequestCategory.objects.get_or_create(
            name="Academic & Grading Inquiry",
            request_type=RequestType.PROBLEM,
            defaults={"default_department": cse, "description": "Scantron recalculations, practical exam queries"},
        )
        cat_welfare, _ = RequestCategory.objects.get_or_create(
            name="Student Services & Campus Issues",
            request_type=RequestType.PROBLEM,
            defaults={"default_department": sa_dept, "description": "Hostel, transportation, cafeteria or security"},
        )

        # Late Class
        cat_late, _ = RequestCategory.objects.get_or_create(
            name="Lecture Delay / Faculty Tardiness",
            request_type=RequestType.LATE_CLASS,
            defaults={"default_department": acad, "description": "Lecture delay exceeding 15 minutes"},
        )

        # 4. Users (All passwords 'Password123!')
        def create_user(username, email, role, dept, first, last, status=User.Status.ACTIVE):
            u, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": email,
                    "first_name": first,
                    "last_name": last,
                    "role": role,
                    "department": dept,
                    "account_status": status,
                    "is_active": status == User.Status.ACTIVE,
                },
            )
            u.set_password("Password123!")
            u.account_status = status
            u.save()
            return u

        # Superuser
        admin = create_user("admin", "admin@atu.edu.so", User.Role.SUPERUSER, None, "Ayaanle", "Farah")
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()

        # Dean Dr. Mohamed Duale
        dean = create_user("m.duale", "m.duale@atu.edu.so", User.Role.DEAN, cse, "Dr. Mohamed", "Duale")
        cse.head = dean
        cse.save()
        StaffProfile.objects.get_or_create(user=dean, defaults={"staff_id": "88204-FCIT", "position": "Dean of Faculty"})

        # Staff Dr. Amina Warsame
        staff_amina = create_user("a.warsame", "a.warsame@atu.edu.so", User.Role.STAFF, cse, "Dr. Amina", "Warsame")
        StaffProfile.objects.get_or_create(user=staff_amina, defaults={"staff_id": "77412-CSE", "position": "Academic Coordinator - CSE"})

        # Staff Eng. Liban Hassan (Pending validation from Dean)
        staff_liban = create_user("l.hassan", "l.hassan@atu.edu.so", User.Role.STAFF, ete, "Eng. Liban", "Hassan", status=User.Status.PENDING)
        staff_liban.created_by = dean
        staff_liban.save()
        StaffProfile.objects.get_or_create(user=staff_liban, defaults={"staff_id": "64109-LAB", "position": "Lab & Hardware Officer"})

        # Academic Office Lead: Dr. Hersi Duale
        acad_lead = create_user("h.duale", "h.duale@atu.edu.so", User.Role.ACADEMIC, acad, "Dr. Hersi", "Duale")
        acad.head = acad_lead
        acad.save()
        StaffProfile.objects.get_or_create(user=acad_lead, defaults={"staff_id": "91002-ACAD", "position": "Senior Academic Registrar"})

        # Director of Student Affairs
        dir_affairs = create_user("director.affairs", "dir.affairs@atu.edu.so", User.Role.DIRECTOR, sa_dept, "Filsan", "Nur")
        sa_dept.head = dir_affairs
        sa_dept.save()
        StaffProfile.objects.get_or_create(user=dir_affairs, defaults={"staff_id": "52011-DIR", "position": "Director of Student Affairs"})

        # Student 1: Fatima Dahir (From Stitch mockups)
        fatima = create_user("fatima.dahir", "student.fatima@atu.edu.so", User.Role.STUDENT, cse, "Fatima", "Dahir")
        StudentProfile.objects.get_or_create(
            user=fatima,
            defaults={"student_id": "ATU-2023-CS-112", "program": "BSc Computer Science & Engineering", "year_of_study": 3, "verified_from_register": True},
        )

        # Student 2: Jamaal Farah
        jamaal = create_user("jamaal.farah", "jamaal.farah@atu.edu.so", User.Role.STUDENT, cse, "Jamaal", "Farah")
        StudentProfile.objects.get_or_create(
            user=jamaal,
            defaults={"student_id": "ATU-2024-CS-045", "program": "BSc Software Engineering", "year_of_study": 2, "verified_from_register": True},
        )

        # Student 3: Hamza Osman (Suspended for demo)
        hamza = create_user("hamza.osman", "h.osman@atu.edu.so", User.Role.STUDENT, cse, "Hamza", "Osman", status=User.Status.SUSPENDED)
        StudentProfile.objects.get_or_create(
            user=hamza,
            defaults={"student_id": "ATU-2023-CS-088", "program": "BSc Computer Science", "year_of_study": 3, "verified_from_register": True},
        )

        # Student 4: Safia Barkhad (Pending Validation)
        safia = create_user("safia.barkhad", "s.barkhad@atu.edu.so", User.Role.STUDENT, cse, "Safia", "Barkhad", status=User.Status.PENDING)
        safia.created_by = admin
        safia.save()
        StudentProfile.objects.get_or_create(
            user=safia,
            defaults={"student_id": "ATU-2025-CS-004", "program": "Intake Freshman 2025", "year_of_study": 1},
        )

        # 5. Seed Requests matching Stitch references
        now = timezone.now()

        # Request 1: ATU-2026-0084 (Absence & Leave - Waiting for Student)
        r84, created = Request.objects.get_or_create(
            reference="ATU-2026-0084",
            defaults={
                "request_type": RequestType.ABSENCE,
                "category": cat_med,
                "student": fatima,
                "title": "Medical Absence Request - Inpatient Care (3 Days)",
                "reason": "Prescribed minor surgical procedure and mandatory post-operative monitored recuperation period at Hargeisa General Hospital.",
                "description": (
                    "I am scheduled for an inpatient surgical operation beginning Monday, March 30th at Hargeisa General Hospital. "
                    "My attending physician advised complete bed rest and clinical observation through Thursday, April 2nd. "
                    "I have already notified group members for the CS-301 Algorithm project and will be able to review slide decks asynchronously once released. "
                    "I kindly request formal excused absences for scheduled lectures and submission waivers for Week 8 problem sets."
                ),
                "department": cse,
                "related_department": cse,
                "assigned_to": staff_amina,
                "status": Status.WAITING,
                "priority": Request.Priority.NORMAL,
                "leave_type": Request.LeaveType.LEAVE,
                "start_date": datetime.date(2026, 3, 30),
                "end_date": datetime.date(2026, 4, 2),
                "created_at": now - datetime.timedelta(days=2),
                "due_at": now + datetime.timedelta(days=2),
            },
        )

        # Attachments for ATU-2026-0084
        dummy_slip = ContentFile(b"%PDF-1.4 sample stamped clinical discharge slip content for ATU portal testing.", name="Hargeisa_General_Hospital_Slip.pdf")
        Attachment.objects.get_or_create(
            request=r84,
            original_name="Hargeisa_General_Hospital_Slip.pdf",
            defaults={
                "file": dummy_slip,
                "size": 1420000,
                "content_type": "application/pdf",
                "uploaded_by": fatima,
            },
        )

        # Timeline comments for ATU-2026-0084
        RequestComment.objects.get_or_create(
            request=r84,
            body="Request submitted by student.",
            kind=RequestComment.Kind.SYSTEM,
            defaults={"author": fatima, "new_status": Status.SUBMITTED, "created_at": now - datetime.timedelta(days=2)},
        )
        RequestComment.objects.get_or_create(
            request=r84,
            body="Dear Fatima, thank you for providing the admission letter. Please upload the discharge summary stamped by the attending physician once issued to formalize excused attendance with the exam board.",
            kind=RequestComment.Kind.RESPONSE,
            defaults={"author": staff_amina, "new_status": Status.WAITING, "created_at": now - datetime.timedelta(hours=2)},
        )
        RequestAssignment.objects.get_or_create(
            request=r84,
            action=RequestAssignment.Action.ASSIGNED,
            defaults={
                "from_department": cse,
                "to_department": cse,
                "assigned_to": staff_amina,
                "performed_by": dean,
                "note": "Assigned to Dr. Amina Warsame for clinical validation.",
                "created_at": now - datetime.timedelta(days=1),
            },
        )

        # Request 2: ATU-2026-0079 (Late Class Report - Under Review)
        Request.objects.get_or_create(
            reference="ATU-2026-0079",
            defaults={
                "request_type": RequestType.LATE_CLASS,
                "category": cat_late,
                "student": fatima,
                "title": "CS-301: Design & Analysis of Algorithms — 42m Tardiness",
                "course": "CS-301 Algorithms",
                "instructor_name": "Prof. Duale",
                "class_date": datetime.date(2026, 3, 22),
                "scheduled_start": datetime.time(8, 30),
                "actual_start": datetime.time(9, 12),
                "description": "Lecture session commenced 42 minutes late due to transit shuttle mechanical delays from East terminus.",
                "department": acad,
                "related_department": cse,
                "assigned_to": acad_lead,
                "status": Status.UNDER_REVIEW,
                "priority": Request.Priority.NORMAL,
                "created_at": now - datetime.timedelta(days=4),
                "due_at": now + datetime.timedelta(days=1),
            },
        )

        # Request 3: ATU-2026-0062 (Student Problem - In Progress)
        Request.objects.get_or_create(
            reference="ATU-2026-0062",
            defaults={
                "request_type": RequestType.PROBLEM,
                "category": cat_lab,
                "student": jamaal,
                "title": "Lab 2 Workstation 14 hardware failure & network port fault",
                "location": "Main Campus Building B, Lab 2, Row 3",
                "description": "The NIC interface does not establish link on station 14 during data structure lab sessions.",
                "department": campus_ops,
                "related_department": cse,
                "assigned_to": staff_amina,
                "status": Status.IN_PROGRESS,
                "priority": Request.Priority.HIGH,
                "created_at": now - datetime.timedelta(days=7),
                "due_at": now - datetime.timedelta(days=1), # Overdue
            },
        )

        # Request 4: ATU-2026-0041 (Absence & Leave - Resolved)
        Request.objects.get_or_create(
            reference="ATU-2026-0041",
            defaults={
                "request_type": RequestType.ABSENCE,
                "category": cat_leave,
                "student": fatima,
                "title": "Official Absence — Inter-university tech symposium delegation",
                "reason": "Representing Abaarso Tech University at national regional technology forum.",
                "description": "Excused attendance for delegation trip from March 5th to March 8th.",
                "department": cse,
                "related_department": cse,
                "assigned_to": dean,
                "status": Status.RESOLVED,
                "decision": Request.Decision.APPROVED,
                "decision_note": "Approved by Dean. Official representation of university.",
                "decided_by": dean,
                "decided_at": now - datetime.timedelta(days=12),
                "start_date": datetime.date(2026, 3, 5),
                "end_date": datetime.date(2026, 3, 8),
                "created_at": now - datetime.timedelta(days=15),
                "resolved_at": now - datetime.timedelta(days=12),
            },
        )

        # Request 5: ATU-2026-0105 (Late Class - Submitted)
        Request.objects.get_or_create(
            reference="ATU-2026-0105",
            defaults={
                "request_type": RequestType.LATE_CLASS,
                "category": cat_late,
                "student": jamaal,
                "title": "MTH-202 Linear Algebra — AV Projector failure & 20m start variance",
                "course": "MTH-202 Linear Algebra",
                "instructor_name": "Dr. Elmi",
                "class_date": datetime.date(2026, 3, 24),
                "scheduled_start": datetime.time(8, 0),
                "actual_start": datetime.time(8, 20),
                "description": "Projector bulb replacement caused 20 minute delay in lecture hall B-201.",
                "department": acad,
                "related_department": nas,
                "status": Status.SUBMITTED,
                "priority": Request.Priority.NORMAL,
                "created_at": now - datetime.timedelta(hours=6),
                "due_at": now + datetime.timedelta(days=3),
            },
        )

        # Notifications for Fatima
        Notification.objects.get_or_create(
            recipient=fatima,
            title="Your Medical Absence (ATU-2026-0084) was assigned to Department Dean.",
            message="Dr. Amina Warsame flagged case for review.",
            kind=Notification.Kind.ASSIGNED,
            request=r84,
            link=r84.get_absolute_url(),
            defaults={"created_at": now - datetime.timedelta(hours=2)},
        )
        Notification.objects.get_or_create(
            recipient=fatima,
            title="Academic Office confirmed late report for lecture session CS-301.",
            message="Variance confirmed with department logistics.",
            kind=Notification.Kind.INFO,
            link="/requests/mine/",
            defaults={"created_at": now - datetime.timedelta(days=1)},
        )

        # Audit Logs
        AuditLog.objects.get_or_create(
            action="request.submitted",
            target_repr="ATU-2026-0084",
            defaults={"actor": fatima, "details": {"type": "absence", "department": "CSE"}, "created_at": now - datetime.timedelta(days=2)},
        )
        AuditLog.objects.get_or_create(
            action="account.created_pending",
            target_repr="Eng. Liban Hassan",
            defaults={"actor": dean, "details": {"department": "ETE", "position": "Lab Officer"}, "created_at": now - datetime.timedelta(days=1)},
        )
        AuditLog.objects.get_or_create(
            action="request.status_changed",
            target_repr="ATU-2026-0084",
            defaults={"actor": staff_amina, "details": {"from": "submitted", "to": "waiting"}, "created_at": now - datetime.timedelta(hours=2)},
        )

        self.stdout.write(self.style.SUCCESS("Demo database successfully seeded!"))
        self.stdout.write("Credentials for all accounts:")
        self.stdout.write("  Superuser:        admin / Password123! (admin@atu.edu.so)")
        self.stdout.write("  Student:          fatima.dahir / Password123! (student.fatima@atu.edu.so)")
        self.stdout.write("  Staff:            a.warsame / Password123! (a.warsame@atu.edu.so)")
        self.stdout.write("  Dean:             m.duale / Password123! (m.duale@atu.edu.so)")
        self.stdout.write("  Academic Office:  h.duale / Password123! (h.duale@atu.edu.so)")
        self.stdout.write("  Student Affairs:  director.affairs / Password123! (dir.affairs@atu.edu.so)")
