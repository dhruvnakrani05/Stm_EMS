from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import CustomUser
from .forms import CustomLoginForm, CustomUserCreationForm, CustomUserUpdateForm
from .decorators import admin_required


def login_view(request):
    """Custom login view with styled form."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            next_url = request.GET.get('next', '/')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = CustomLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Logout and redirect to login page."""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


@admin_required
def user_list(request):
    """List all system users. Admin only."""
    users = CustomUser.objects.all().order_by('-created_at')
    return render(request, 'accounts/user_list.html', {'users': users})


@admin_required
def user_create(request):
    """Create a new system user. Admin only."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'User "{user.username}" created successfully with {user.get_role_display()} role.')
            return redirect('accounts:user_list')
    else:
        form = CustomUserCreationForm()

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Create New User',
        'button_text': 'Create User',
    })


@admin_required
def user_edit(request, pk):
    """Edit an existing user. Admin only."""
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        form = CustomUserUpdateForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'User "{user.username}" updated successfully.')
            return redirect('accounts:user_list')
    else:
        form = CustomUserUpdateForm(instance=user)

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': f'Edit User: {user.username}',
        'button_text': 'Update User',
        'editing': True,
    })


@admin_required
def user_delete(request, pk):
    """Delete a user. Admin only."""
    user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        if user == request.user:
            messages.error(request, 'You cannot delete your own account.')
        else:
            username = user.username
            user.delete()
            messages.success(request, f'User "{username}" deleted successfully.')
        return redirect('accounts:user_list')

    return render(request, 'accounts/user_confirm_delete.html', {'user_obj': user})
