from django import forms
from django.utils import timezone

from accounts.models import Department, User

from .models import Request, RequestCategory, RequestType, Status
from .validators import (
    validate_absence_dates,
    validate_course_identifier,
    validate_meaningful_text,
    validate_upload,
)


# --- Widgets / helpers --------------------------------------------------------------
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Accepts several files; each is validated individually."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png,.docx"}))
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            files = [single(d, initial) for d in data if d]
        else:
            files = [single(data, initial)] if data else []
        if len(files) > 5:
            raise forms.ValidationError("You can attach at most 5 files at a time.")
        for f in files:
            validate_upload(f)
        return files


class StyledFormMixin:
    """Applies design-system classes to every widget."""

    def _style_fields(self):
        for name, field in self.fields.items():
            w = field.widget
            if isinstance(w, (forms.CheckboxInput,)):
                w.attrs.setdefault("class", "checkbox")
            elif isinstance(w, (forms.ClearableFileInput, forms.FileInput)):
                w.attrs.setdefault("class", "file-input")
            elif isinstance(w, forms.Select):
                w.attrs.setdefault("class", "input select")
            elif isinstance(w, forms.Textarea):
                w.attrs.setdefault("class", "input textarea")
                w.attrs.setdefault("rows", 5)
            else:
                w.attrs.setdefault("class", "input")
            w.attrs.setdefault("id", f"id_{self.prefix + '-' if self.prefix else ''}{name}")


class DeclarationMixin(forms.Form):
    declaration = forms.BooleanField(
        required=True,
        label="I declare that the information provided is accurate and complies with the "
              "Abaarso Tech University student code of conduct.",
    )


# --- Submission forms -------------------------------------------------------------------
class AbsenceRequestForm(StyledFormMixin, DeclarationMixin, forms.Form):
    request_type = RequestType.ABSENCE

    leave_type = forms.ChoiceField(label="Request type", choices=Request.LeaveType.choices)
    category = forms.ModelChoiceField(label="Reason category", queryset=RequestCategory.objects.none())
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(label="Reason / short justification", max_length=120)
    description = forms.CharField(
        label="Additional explanation & affected courses", widget=forms.Textarea,
        help_text="Include course codes affected. Do not include unnecessary medical or personal detail.",
    )
    attachments = MultipleFileField(label="Supporting documents")

    def __init__(self, *args, student=None, **kwargs):
        self.student = student
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = RequestCategory.objects.filter(
            request_type=RequestType.ABSENCE, is_active=True
        )
        self._style_fields()

    def clean_reason(self):
        return validate_meaningful_text(self.cleaned_data.get("reason"), "Reason", min_length=5, min_words=2)

    def clean_description(self):
        return validate_meaningful_text(
            self.cleaned_data.get("description"), "Course details and explanation", min_length=15, min_words=3
        )

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if start and end:
            try:
                validate_absence_dates(start, end)
            except forms.ValidationError as e:
                self.add_error("start_date" if "start" in str(e).lower() else "end_date", e.message)

        from core.models import SiteSettings
        site_settings = SiteSettings.load()

        # Check evidence requirement (doctor's note, hospital discharge slip, or official documentation)
        attachments = data.get("attachments") or []
        if site_settings.absence_requires_document and not attachments:
            self.add_error(
                "attachments",
                "Official supporting documentation (e.g. medical slip, clinic note, or official letter) is required for absence & leave requests."
            )

        # Check overlapping dates with existing active/approved absence requests
        if self.student and site_settings.block_overlapping_absence and start and end:
            from .models import OPEN_STATUSES, Status
            overlapping = Request.objects.filter(
                student=self.student,
                request_type=RequestType.ABSENCE,
                status__in=OPEN_STATUSES + [Status.RESOLVED],
                start_date__lte=end,
                end_date__gte=start,
            ).first()
            if overlapping:
                self.add_error(
                    "start_date",
                    f"You already have a request ({overlapping.reference}) covering overlapping dates "
                    f"({overlapping.start_date:%b %d, %Y} to {overlapping.end_date:%b %d, %Y}). "
                    f"Duplicate absence requests for overlapping periods are blocked."
                )

        if data.get("leave_type") and data.get("category") and start and end and not self.errors:
            days = (end - start).days + 1
            data["title"] = (
                f"{dict(Request.LeaveType.choices)[data['leave_type']]} – {data['category'].name} "
                f"({days} day{'s' if days != 1 else ''})"
            )
        return data


class ProblemReportForm(StyledFormMixin, DeclarationMixin, forms.Form):
    request_type = RequestType.PROBLEM

    category = forms.ModelChoiceField(queryset=RequestCategory.objects.none())
    department = forms.ModelChoiceField(
        label="Target Department / Office (optional)",
        queryset=Department.objects.none(),
        required=False,
        empty_label="Automatic Routing (Category Default / My Department)",
        help_text="Direct ticket to a specific department or leave blank for automatic routing.",
    )
    title = forms.CharField(max_length=150, help_text="A short summary of the problem.")
    description = forms.CharField(widget=forms.Textarea)
    location = forms.CharField(max_length=150, required=False, help_text="Optional — building, room or area.")
    is_confidential = forms.BooleanField(
        required=False, label="This is a sensitive matter — restrict access to authorized staff only",
    )
    attachments = MultipleFileField(label="Attachments (optional)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = RequestCategory.objects.filter(
            request_type=RequestType.PROBLEM, is_active=True
        )
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self._style_fields()

    def clean_title(self):
        return validate_meaningful_text(self.cleaned_data.get("title"), "Summary title", min_length=8, min_words=2)

    def clean_description(self):
        return validate_meaningful_text(self.cleaned_data.get("description"), "Problem description", min_length=20, min_words=3)

    def clean_location(self):
        loc = (self.cleaned_data.get("location") or "").strip()
        if loc and len(loc) > 150:
            raise forms.ValidationError("Location must not exceed 150 characters.")
        return loc


class LateClassForm(StyledFormMixin, DeclarationMixin, forms.Form):
    request_type = RequestType.LATE_CLASS

    course = forms.CharField(label="Course or subject", max_length=150, help_text="e.g. CS-301 Algorithms")
    department = forms.ModelChoiceField(label="Department", queryset=Department.objects.none())
    instructor_name = forms.CharField(label="Instructor name (if known)", max_length=150, required=False)
    class_date = forms.DateField(label="Scheduled class date", widget=forms.DateInput(attrs={"type": "date"}))
    scheduled_start = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    actual_start = forms.TimeField(
        label="Actual start time", required=False, widget=forms.TimeInput(attrs={"type": "time"}),
        help_text="Leave blank if the class did not start.",
    )
    class_did_not_start = forms.BooleanField(required=False, label="The class did not start at all")
    description = forms.CharField(label="Description / additional information", widget=forms.Textarea)

    def __init__(self, *args, student=None, **kwargs):
        self.student = student
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.filter(
            is_active=True, kind=Department.Kind.ACADEMIC
        )
        self.fields["description"].widget.attrs["rows"] = 4
        self._style_fields()

    def clean_course(self):
        return validate_course_identifier(self.cleaned_data.get("course"))

    def clean_description(self):
        return validate_meaningful_text(self.cleaned_data.get("description"), "Class report details", min_length=15, min_words=2)

    def clean(self):
        data = super().clean()
        cdate = data.get("class_date")
        if cdate:
            today = timezone.localdate()
            if cdate > today:
                self.add_error("class_date", "The class date cannot be in the future.")
            elif (today - cdate).days > 14:
                self.add_error("class_date", "Late class reports must be submitted within 14 days of the lecture.")
        sched, actual = data.get("scheduled_start"), data.get("actual_start")
        if not data.get("class_did_not_start"):
            if not actual:
                self.add_error("actual_start", "Enter the actual start time, or tick 'did not start'.")
            elif sched and actual <= sched:
                self.add_error("actual_start", "Actual start must be later than the scheduled start.")
        else:
            data["actual_start"] = None

        if self.student and data.get("course") and cdate:
            from .models import OPEN_STATUSES
            existing_late = Request.objects.filter(
                student=self.student,
                request_type=RequestType.LATE_CLASS,
                course__iexact=data["course"].strip(),
                class_date=cdate,
                status__in=OPEN_STATUSES,
            ).first()
            if existing_late:
                self.add_error(
                    "course",
                    f"You have already reported a late class for '{data['course']}' on {cdate:%b %d, %Y} "
                    f"({existing_late.reference}). Duplicate submissions for the same session are blocked."
                )

        if data.get("course") and cdate and not self.errors:
            data["title"] = f"{data['course']} – late start on {cdate:%b %d, %Y}"
        data["category"] = RequestCategory.objects.filter(
            request_type=RequestType.LATE_CLASS, is_active=True
        ).first()
        return data


SUBMISSION_FORMS = {
    RequestType.ABSENCE: AbsenceRequestForm,
    RequestType.PROBLEM: ProblemReportForm,
    RequestType.LATE_CLASS: LateClassForm,
}


# --- Case action forms ---------------------------------------------------------------------
class CommentForm(StyledFormMixin, forms.Form):
    body = forms.CharField(label="Message", widget=forms.Textarea(attrs={"rows": 4}))
    is_internal = forms.BooleanField(required=False, label="Internal note (hidden from student)")
    attachments = MultipleFileField(label="Attach files")

    def __init__(self, *args, allow_internal=False, force_internal=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not allow_internal:
            del self.fields["is_internal"]
        elif force_internal:
            self.fields["is_internal"].initial = True
            self.fields["is_internal"].disabled = True
        self._style_fields()

    def clean_body(self):
        return validate_meaningful_text(self.cleaned_data.get("body"), "Message", min_length=4, min_words=1)


class StatusForm(StyledFormMixin, forms.Form):
    status = forms.ChoiceField(label="New status")
    message = forms.CharField(
        label="Message to student / decision explanation", required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, choices=(), request_obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = choices
        self.request_obj = request_obj
        self._style_fields()

    def clean(self):
        data = super().clean()
        status, msg = data.get("status"), (data.get("message") or "").strip()
        needs_message = {Status.WAITING: "Explain what information the student must provide.",
                         Status.REJECTED: "A rejection must include an explanation."}
        if status in needs_message and not msg:
            self.add_error("message", needs_message[status])
        if (self.request_obj is not None and self.request_obj.request_type == RequestType.ABSENCE
                and status == Status.RESOLVED and not msg):
            self.add_error("message", "Record the approval decision and any conditions.")
        return data


class AssignForm(StyledFormMixin, forms.Form):
    staff = forms.ModelChoiceField(label="Assign to", queryset=User.objects.none())
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, department=None, note_required=False, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(account_status=User.Status.ACTIVE, department=department).exclude(
            role__in=[User.Role.STUDENT, User.Role.SUPERUSER]
        ) if department else User.objects.none()
        self.fields["staff"].queryset = qs
        self.fields["staff"].label_from_instance = lambda u: f"{u.display_name} — {u.subtitle}"
        self.fields["note"].required = note_required
        self._style_fields()


class EscalateForm(StyledFormMixin, forms.Form):
    target = forms.ChoiceField(label="Escalate to")
    note = forms.CharField(label="Reason for escalation", widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, request_obj=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = []
        dept = request_obj.department if request_obj else None
        if dept and dept.head_id and dept.head_id != user.id:
            choices.append(("head", f"Head of {dept.name} ({dept.head.display_name})"))
        for d in Department.objects.filter(is_active=True).exclude(pk=getattr(dept, "pk", None)):
            choices.append((str(d.pk), f"{d.name} · {d.get_kind_display()}"))
        self.fields["target"].choices = choices
        self._style_fields()

    def clean_target(self):
        value = self.cleaned_data["target"]
        if value == "head":
            return "head"
        try:
            return Department.objects.get(pk=int(value), is_active=True)
        except (ValueError, Department.DoesNotExist):
            raise forms.ValidationError("Choose a valid department or office.")


class RequestFilterForm(forms.Form):
    q = forms.CharField(required=False)
    type = forms.ChoiceField(required=False, choices=[("", "All types")] + list(RequestType.choices))
    status = forms.ChoiceField(required=False, choices=[("", "All statuses")] + list(Status.choices))
    department = forms.ModelChoiceField(
        required=False, queryset=Department.objects.filter(is_active=True), empty_label="All departments"
    )
    overdue = forms.BooleanField(required=False)
