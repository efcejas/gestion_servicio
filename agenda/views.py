from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import CreateView, UpdateView

from .models import AgendaItem, NotaPersonal


class AgendaItemCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Vista para crear un nuevo item de agenda"""
    model = AgendaItem
    template_name = 'agenda/agenda_form.html'
    fields = ['titulo', 'fecha', 'hora_inicio', 'hora_fin', 'tipo', 'es_importante', 'descripcion', 'completado']
    success_url = reverse_lazy('home')
    
    def test_func(self):
        """Solo permite acceso a usuarios staff o superusuarios"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def form_valid(self, form):
        """Asigna el usuario actual como creador"""
        form.instance.creado_por = self.request.user
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Nuevo evento de agenda'
        context['boton_texto'] = 'Crear evento'
        return context


class AgendaItemUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Vista para editar un item de agenda existente"""
    model = AgendaItem
    template_name = 'agenda/agenda_form.html'
    fields = ['titulo', 'fecha', 'hora_inicio', 'hora_fin', 'tipo', 'es_importante', 'descripcion', 'completado']
    success_url = reverse_lazy('home')
    
    def test_func(self):
        """Solo permite editar al creador del item"""
        obj = self.get_object()
        return obj.creado_por == self.request.user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Editar evento de agenda'
        context['boton_texto'] = 'Guardar cambios'
        return context


class NotaPersonalCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Vista para crear una nueva nota personal"""
    model = NotaPersonal
    template_name = 'agenda/nota_form.html'
    fields = ['titulo', 'contenido', 'fijada']
    success_url = reverse_lazy('home')
    
    def test_func(self):
        """Solo permite acceso a usuarios staff o superusuarios"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def form_valid(self, form):
        """Asigna el usuario actual como creador"""
        form.instance.creado_por = self.request.user
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Nueva nota'
        context['boton_texto'] = 'Crear nota'
        return context


class NotaPersonalUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Vista para editar una nota personal existente"""
    model = NotaPersonal
    template_name = 'agenda/nota_form.html'
    fields = ['titulo', 'contenido', 'fijada']
    success_url = reverse_lazy('home')
    
    def test_func(self):
        """Solo permite editar al creador de la nota"""
        obj = self.get_object()
        return obj.creado_por == self.request.user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Editar nota'
        context['boton_texto'] = 'Guardar cambios'
        return context


class AgendaItemToggleCompletoView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vista para marcar/desmarcar un item de agenda como completado"""
    
    def test_func(self):
        """Solo permite acceso a staff/superusuarios y debe ser el dueño"""
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            return False
        obj = get_object_or_404(AgendaItem, pk=self.kwargs.get('pk'))
        return obj.creado_por == self.request.user
    
    def post(self, request, *args, **kwargs):
        """Toggle del estado completado"""
        obj = get_object_or_404(AgendaItem, pk=kwargs.get('pk'))
        
        # Verificar permisos nuevamente por seguridad
        if obj.creado_por != request.user:
            return redirect('home')
        
        # Toggle del campo completado
        obj.completado = not obj.completado
        obj.save()
        
        # Redirigir al dashboard
        return redirect(reverse('home'))


class NotaPersonalToggleFijadaView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Vista para fijar/desfijar una nota personal"""
    
    def test_func(self):
        """Solo permite acceso a staff/superusuarios y debe ser el dueño"""
        if not (self.request.user.is_staff or self.request.user.is_superuser):
            return False
        obj = get_object_or_404(NotaPersonal, pk=self.kwargs.get('pk'))
        return obj.creado_por == self.request.user
    
    def post(self, request, *args, **kwargs):
        """Toggle del estado fijada"""
        obj = get_object_or_404(NotaPersonal, pk=kwargs.get('pk'))
        
        # Verificar permisos nuevamente por seguridad
        if obj.creado_por != request.user:
            return redirect('home')
        
        # Toggle del campo fijada
        obj.fijada = not obj.fijada
        obj.save()
        
        # Redirigir al dashboard
        return redirect(reverse('home'))
