from django.test import TestCase

from .choices import ComponentGroupCollapseChoices, ComponentStatusChoices
from .models import Component, ComponentGroup


class ComponentModelTests(TestCase):
    def test_default_status_is_operational(self):
        component = Component.objects.create(name="API Server")
        self.assertEqual(component.status, ComponentStatusChoices.OPERATIONAL)

    def test_str_returns_name(self):
        component = Component.objects.create(name="API Server")
        self.assertEqual(str(component), "API Server")

    def test_status_color_matches_choice_definition(self):
        component = Component.objects.create(
            name="API Server", status=ComponentStatusChoices.MAJOR_OUTAGE
        )
        self.assertEqual(component.get_status_color(), "bg-red-500")
        self.assertEqual(component.get_status_text_color(), "text-red-500")

    def test_default_ordering_is_by_group_then_order_then_pk(self):
        group = ComponentGroup.objects.create(name="Infra")
        second = Component.objects.create(name="Second", component_group=group, order=2)
        first = Component.objects.create(name="First", component_group=group, order=1)
        self.assertEqual(list(Component.objects.filter(component_group=group)), [first, second])


class ComponentGroupModelTests(TestCase):
    def test_should_expand_true_when_a_component_is_not_operational(self):
        group = ComponentGroup.objects.create(
            name="Infra", collapse=ComponentGroupCollapseChoices.ON_ISSUE
        )
        Component.objects.create(
            name="API Server", component_group=group, status=ComponentStatusChoices.MAJOR_OUTAGE
        )
        self.assertEqual(group.should_expand, "true")

    def test_should_expand_false_when_all_components_operational(self):
        group = ComponentGroup.objects.create(
            name="Infra", collapse=ComponentGroupCollapseChoices.ON_ISSUE
        )
        Component.objects.create(
            name="API Server", component_group=group, status=ComponentStatusChoices.OPERATIONAL
        )
        self.assertEqual(group.should_expand, "false")

    def test_str_returns_name(self):
        group = ComponentGroup.objects.create(name="Infra")
        self.assertEqual(str(group), "Infra")
