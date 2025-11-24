from django.shortcuts import render
from django.contrib import messages

def test_toast(request):
    test_type = request.GET.get('test')
    
    if test_type == 'success':
        messages.success(request, 'Este es un mensaje de éxito!')
    elif test_type == 'error':
        messages.error(request, 'Este es un mensaje de error!')
    elif test_type == 'info':
        messages.info(request, 'Este es un mensaje informativo!')
    elif test_type == 'warning':
        messages.warning(request, 'Este es un mensaje de advertencia!')
    
    return render(request, 'test_toast.html')