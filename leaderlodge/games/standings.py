from django.db.models import F, FloatField
from django.db.models.functions import Cast


def standings_weight_expression(prefix: str = "game__"):
    double_field = f"{prefix}double_weight"
    half_field = f"{prefix}half_weight"
    return Cast(F(double_field), FloatField()) / Cast(F(half_field), FloatField())
