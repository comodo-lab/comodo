import src.saved_selector as ss

DATA = [{"name": "a", "value": 1}]
META = {"file": "a.yaml", "name": "a", "saved_name": "a", "saved": DATA}


class TestGetSaveButton:
    def test_saved(self):
        assert ss.get_save_button(DATA, META) == ("Saved", "success", True)

    def test_changed_data(self):
        data = [{"name": "a", "value": 2}]
        assert ss.get_save_button(data, META) == ("Save changes", "success", False)

    def test_renamed(self):
        meta = {**META, "name": "b"}
        assert ss.get_save_button(DATA, meta) == ("Save changes", "success", False)

    def test_not_loaded(self):
        assert ss.get_save_button(None, META)[2] is True
        assert ss.get_save_button(DATA, None)[2] is True
