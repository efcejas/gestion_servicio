from django.shortcuts import render, redirect
from django.views.generic.edit import CreateView, UpdateView
from django.urls import reverse_lazy
from .forms import CustomUserCreationForm, CompletarPerfilForm, CustomUserChangeForm
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages


class UserRegisterView(SuccessMessageMixin, CreateView):
    """Vista de registro simplificada - solo datos básicos."""
    form_class = CustomUserCreationForm
    template_name = 'registration/register_tailwind.html'
    success_url = reverse_lazy('login')
    success_message = "Tu cuenta ha sido creada exitosamente. Ahora puedes iniciar sesión."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hide_navbar'] = True
        return context


@login_required
def completar_perfil(request):
    """
    Vista para completar el perfil del usuario post-registro.
    Solo accesible para usuarios con perfil incompleto.
    """
    # Si el perfil ya está completo, redirigir al home
    if request.user.perfil_completo:
        messages.info(request, 'Tu perfil ya está completo.')
        return redirect('home')
    
    if request.method == 'POST':
        form = CompletarPerfilForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                '¡Perfil completado exitosamente! Ahora tienes acceso completo al sistema.'
            )
            return redirect('home')
    else:
        form = CompletarPerfilForm(instance=request.user)
    
    return render(request, 'accounts/completar_perfil.html', {
        'form': form,
        'hide_navbar': False,  # Mostrar navbar pero con acceso limitado
    })


@login_required
def editar_perfil(request):
    """
    Vista para editar el perfil del usuario.
    Permite modificar datos personales y preferencias.
    """
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Tu perfil ha sido actualizado exitosamente.'
            )
            return redirect('accounts:editar_perfil')
    else:
        form = CustomUserChangeForm(instance=request.user)
    
    return render(request, 'accounts/editar_perfil.html', {
        'form': form,
    })