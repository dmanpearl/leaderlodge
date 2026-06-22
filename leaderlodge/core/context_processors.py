from leaderlodge.core.decorators import demo_mode_enabled
from leaderlodge.groups.services import get_demo_group


def demo_context(request):
    demo_group = get_demo_group() if demo_mode_enabled() else None
    return {
        "demo_mode_enabled": demo_mode_enabled(),
        "demo_group": demo_group,
        "is_visitor": not request.user.is_authenticated,
    }
