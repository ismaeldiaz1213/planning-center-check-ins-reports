from backfill_bus_class import assign_class, plan_assignments


def _rider(first="Ana", route="Ruta 3"):
    return {"first_name": first, "last_name": "Lopez", "location": route}


class TestAssignClass:
    def test_grade_and_gender_pick_the_class(self):
        assert assign_class(7, "Male") == '"C" 7th Boys'
        assert assign_class(8, "Female") == '"C" 8th Girls'
        assert assign_class(9, "Male") == '"C" 9th &10th Boys'
        assert assign_class(10, "Female") == '"C" 9th &10th Girls'

    def test_eleventh_and_twelfth_are_coed(self):
        assert assign_class(11, "Male") == '"C" 11th &12th Coed'
        assert assign_class(12, "") == '"C" 11th &12th Coed'

    def test_outside_seven_to_twelve_is_none(self):
        assert assign_class(6, "Male") is None
        assert assign_class(None, "Male") is None

    def test_unknown_gender_is_none_below_eleventh(self):
        assert assign_class(8, "") is None


class TestPlanAssignments:
    def test_people_grade_wins_over_class(self):
        plan, skipped = plan_assignments(
            {"p1": _rider()},
            {"p1": "7th Grade Boys"},
            {"p1": {"grade_num": 8, "gender": "Male", "birthday": "2012-01-01"}},
            max_age=20,
        )
        assert [m["account_center_person_id"] for m in plan['"C" 8th Boys']] == ["p1"]
        assert skipped == []

    def test_falls_back_to_regular_class_when_no_grade(self):
        plan, _ = plan_assignments(
            {"p1": _rider()},
            {"p1": "9th and 10th Grade Girls"},
            {"p1": {"grade_num": None, "gender": "Female", "birthday": ""}},
            max_age=20,
        )
        assert plan['"C" 9th &10th Girls'][0]["grade_source"] == "class"

    def test_adults_and_younger_kids_are_left_out_silently(self):
        plan, skipped = plan_assignments(
            {"adult": _rider("Adult"), "kid": _rider("Kid")},
            {"adult": "7th Grade Boys"},  # e.g. a parent who sits in with the class
            {
                "adult": {"grade_num": None, "gender": "Male", "birthday": "1990-01-01"},
                "kid": {"grade_num": 4, "gender": "Female", "birthday": "2016-01-01"},
            },
            max_age=20,
        )
        assert plan == {}
        assert skipped == []

    def test_teen_with_no_grade_anywhere_is_reported(self):
        plan, skipped = plan_assignments(
            {"p1": _rider()},
            {"p1": "College and Career"},  # attended, but not a class that implies a grade
            {"p1": {"grade_num": None, "gender": "Female", "birthday": "2011-01-01"}},
            max_age=20,
        )
        assert plan == {}
        assert len(skipped) == 1 and "no grade" in skipped[0][1]

    def test_riders_who_never_attended_escuela_are_left_out_by_default(self):
        riders = {"attends": _rider("Attends"), "bus_only": _rider("BusOnly")}
        details = {pid: {"grade_num": 8, "gender": "Male", "birthday": "2012-01-01"} for pid in riders}
        escuela = {"attends": "8th Grade Boys"}

        plan, skipped = plan_assignments(riders, escuela, details, max_age=20)
        assert [m["account_center_person_id"] for m in plan['"C" 8th Boys']] == ["attends"]
        assert skipped == []

        plan, _ = plan_assignments(riders, escuela, details, max_age=20, require_escuela=False)
        assert len(plan['"C" 8th Boys']) == 2
