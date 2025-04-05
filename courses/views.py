from braces.views import CsrfExemptMixin, JSONResponseMixin
from django.apps import apps
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.cache import cache
from django.db.models import Count
from django.forms import modelform_factory
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView
from django.views.generic.base import TemplateResponseMixin, View
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.list import ListView

from students.forms import CourseEnrollForm
from .forms import ModuleFormSet
from .models import Course, Module, Content, Subject


class OwnerMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(owner=self.request.user)


class OwnerEditMixin:
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class OwnerCourseMixin(OwnerMixin, LoginRequiredMixin, PermissionRequiredMixin):
    template_name = 'courses/manage/course/form.html'
    model = Course
    fields = ['subject', 'title', 'slug', 'overview']
    success_url = reverse_lazy('manage_course_list')


class ManageCourseListView(OwnerCourseMixin, ListView):
    permission_required = 'courses.view_course'
    template_name = 'courses/manage/course/list.html'


class CourseCreateView(OwnerCourseMixin, OwnerEditMixin, CreateView):
    permission_required = 'courses.add_course'


class CourseUpdateView(OwnerCourseMixin, OwnerEditMixin, UpdateView):
    permission_required = 'courses.change_course'


class CourseDeleteView(OwnerCourseMixin, DeleteView):
    permission_required = 'courses.delete_course'
    template_name = 'courses/manage/course/delete.html'


class CourseModuleUpdateView(TemplateResponseMixin, View):
    template_name = 'courses/manage/module/formset.html'
    course = None

    def get_formset(self, **kwargs):
        return ModuleFormSet(instance=self.course, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        pk = kwargs.get('pk')
        self.course = get_object_or_404(
            Course,
            id=pk,
            owner=self.request.user,
        )
        return super().dispatch(request, pk=pk)

    def get(self, request, *args, **kwargs):
        formset = self.get_formset()
        return self.render_to_response({
            'formset': formset,
            'course': self.course,
        })

    def post(self, request, *args, **kwargs):
        formset = self.get_formset(data=request.POST)
        if formset.is_valid():
            formset.save()
            return redirect('manage_course_list')
        return self.render_to_response({
            'formset': formset,
            'course': self.course,
        })


class ContentCreateUpdateView(TemplateResponseMixin, View):
    module = None
    model = None
    obj = None
    template_name = None

    def get_model(self, model_name):
        if model_name in ['text', 'video', 'image', 'file']:
            return apps.get_model(
                app_label='courses',
                model_name=model_name
            )
        return None

    def get_form(self, model, *args, **kwargs):
        Form = modelform_factory(
            model=model,
            exclude=['owner', 'order', 'created', 'updated']
        )
        return Form(*args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        module_id = kwargs.get('module_id')
        model_name = kwargs.get('model_name')
        id = kwargs.get('id')
        self.module = get_object_or_404(
            Module,
            pk=module_id,
            course__owner=self.request.user,
        )
        self.model = self.get_model(model_name)
        if id:
            self.obj = get_object_or_404(
                Module,
                pk=id,
                course__owner=self.request.user,
            )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = self.get_form(self.model, instance=self.obj)
        return self.render_to_response({
            'form': form,
            'object': self.obj,
            'module': self.module,
        })

    def post(self, request, *args, **kwargs):
        form = self.get_form(self.model, request.POST, request.FILES, instance=self.obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner = request.user
            obj.save()
            if not id:
                Content.objects.create(module=self.module, item=obj)
            return redirect('module_content_list', self.module.id)
        return self.render_to_response({
            'form': form,
            'object': self.obj,
        })


class ContentDeleteView(View):
    def post(self, request, *args, **kwargs):
        id = kwargs.get('id')
        content = get_object_or_404(Content, pk=id, module__course__owner=request.user)
        module = content.module
        content.item.delete()
        content.delete()
        return redirect('manage_course_list', module.id)


class ModuleContentListView(TemplateResponseMixin, View):
    template_name = 'courses/manage/module/formset.html'

    def get(self, request, *args, **kwargs):
        module_id = kwargs.get('module')
        module = get_object_or_404(Module, id=module_id, course__owner=request.user)
        self.render_to_response(
            {
                'module': module,
            }
        )


class ModuleOrderView(CsrfExemptMixin, JSONResponseMixin, View):
    def post(self, request, *args, **kwargs):
        for id, order in self.request_json.items():
            try:
                module = Module.objects.filter(id=id, course__owner=request.user) \
                    .update(order=order)
                return self.render_json_response({'saved': 'OK'})
            except Module.DoesNotExist:
                pass
        return self.render_json_response({'saved': 'NO'})


class ContentOrderView(CsrfExemptMixin, JSONResponseMixin, View):
    def post(self, request, *args, **kwargs):
        for id, order in self.request_json.items():
            try:
                content = Content.objects.filter(id=id, module__course__owner=request.user) \
                    .update(order=order)
                return self.render_json_response({'saved': 'OK'})
            except Content.DoesNotExist:
                pass
        return self.render_json_response({'saved': 'NO'})


class CourseListView(TemplateResponseMixin, View):
    model = Course
    template_name = 'courses/course/list.html'

    def get(self, request, *args, **kwargs):
        subjects = cache.get('all_subjects')
        if not subjects:
            subjects = Subject.objects.annotate(
                total_courses=Count('courses')
            )
            cache.set('all_subjects', subjects)

        all_courses = Course.objects.annotate(
            total_modules=Count('modules')
        )
        subject = request.GET.get('subject')
        if subject:
            subject = get_object_or_404(Subject, slug=subject)
            key = f'subject_{subject.id}_courses'
            courses = cache.get(key)
            if not courses:
                courses = all_courses.filter(subject=subject)
                cache.set(key, courses)
        else:
            courses = cache.get('all_courses')
            if not courses:
                courses = all_courses
                cache.set('all_courses', courses)
        return self.render_to_response({
            'subjects': subjects,
            'subject': subject,
            'courses': courses,
        })


class CourseDetailView(DetailView):
    model = Course
    template_name = 'courses/course/detail.html'
    context_object_name = 'course'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'
    queryset = Course.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['enroll_form'] = CourseEnrollForm(
            initial={'course': self.object}
        )
        return context
