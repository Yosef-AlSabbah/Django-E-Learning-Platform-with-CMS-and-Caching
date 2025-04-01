from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, ListView, DetailView

from courses.models import Course
from students.forms import CourseEnrollForm


class StudentRegistrationView(CreateView):
    template_name = 'courses/student/registration.html'
    form_class = UserCreationForm
    success_url = reverse_lazy('student_course_list')

    def form_valid(self, form):
        result = super().form_valid(form)
        cd = form.cleaned_data
        user = authenticate(
            username=cd['username'],
            password=cd['password1']
        )
        login(self.request, user)
        return result


class StudentEnrollCourseView(LoginRequiredMixin, FormView):
    course = None
    form_class = CourseEnrollForm

    def form_valid(self, form):
        self.course = form.cleaned_data['course']
        self.course.students.add(self.request.user)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('student_course_detail', args=[self.course.id])


class StudentCourseListView(LoginRequiredMixin, ListView):
    model = Course
    template_name = 'courses/student/course/list.html'

    def get_queryset(self):
        return self.request.user.courses_joined.all()


class StudentCourseDetailView(LoginRequiredMixin, DetailView):
    model = Course
    template_name = 'courses/student/course/detail.html'

    def get_queryset(self):
        return self.request.user.courses_joined.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        if 'module_id' in kwargs:
            context['module'] = course.modules.get(id=kwargs['module_id'])
        else:
            context['module'] = course.modules.all()[0]

        return context
