from django import forms

from courses.models import Course


class CourseEnrollForm(forms.Form):
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        widget=forms.HiddenInput,
    )

    def __init__(self, *args, **kwargs):
        super(CourseEnrollForm, self).__init__(*args, **kwargs)
        self.files['course'].queryset = Course.objects.all()
