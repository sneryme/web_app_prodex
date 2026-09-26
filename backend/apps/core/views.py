from django.http import JsonResponse

def health(request):
    return JsonResponse({"status": "ok", "service": "pez-digital-api"})
