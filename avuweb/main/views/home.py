from django.shortcuts import render


BENEFITS = [
    {
        "title": "Comunidad AVU",
        "description": "Conectá con otras personas veganas para compartir recursos y apoyo mutuo.",
    },
    {
        "title": "Formación y recursos",
        "description": "Accedé a talleres, guías y materiales que promueven el veganismo en Uruguay.",
    },
    {
        "title": "Incidencia y voluntariado",
        "description": "Sumate a campañas y comisiones para amplificar el impacto de la organización.",
    },
]


def landing(request):
    context = {"benefits": BENEFITS}

    if request.method == "POST":
        context["message"] = "Gracias por escribirnos. Te responderemos pronto."
        if request.headers.get("HX-Request"):
            return render(request, "main/includes/contact_success.html", context, status=201)
        return render(request, "main/home.html", context, status=201)

    return render(request, "main/home.html", context)


def benefits_partial(request):
    return render(request, "main/includes/benefits.html", {"benefits": BENEFITS})
