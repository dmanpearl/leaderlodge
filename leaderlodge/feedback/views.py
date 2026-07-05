from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from leaderlodge.feedback.email import send_feedback_confirmation_email
from leaderlodge.feedback.forms import FeedbackForm


@login_required
def feedback_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.full_clean()
            feedback.save()
            try:
                send_feedback_confirmation_email(feedback=feedback)
            except ValueError:
                messages.warning(
                    request,
                    "Your feedback was saved, but we could not email a confirmation "
                    "because your account has no email address on file.",
                )
            except Exception:
                messages.warning(
                    request,
                    "Your feedback was saved, but we could not send the confirmation "
                    "email. Please try again later if you need a copy.",
                )
            else:
                messages.success(
                    request,
                    "Thanks for your feedback. We sent a confirmation to your email.",
                )
            return redirect("feedback:thanks")
    else:
        form = FeedbackForm()

    return render(
        request,
        "feedback/feedback_form.html",
        {"form": form},
    )


@login_required
def feedback_thanks(request: HttpRequest) -> HttpResponse:
    return render(request, "feedback/feedback_thanks.html")
