def base_template(request):
    ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    return {'base_template': 'crm/_modal_base.html' if ajax else 'base.html'}
