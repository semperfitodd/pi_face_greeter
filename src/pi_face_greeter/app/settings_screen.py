from __future__ import annotations

import logging
from typing import Any, Callable

from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from pi_face_greeter.app.camera_source import CameraSource
from pi_face_greeter.app.people_store import (
    PersonAlreadyExistsError,
    PersonNotFoundError,
    PeopleStoreError,
    delete_person,
    list_people,
    update_person_name,
)
from pi_face_greeter.enrollment import enroll_from_frames

logger = logging.getLogger("pi_face_greeter.settings_screen")


class SettingsScreen(Screen):
    def __init__(
        self,
        camera_source: CameraSource | None = None,
        enrollment_cfg: dict[str, Any] | None = None,
        detection_cfg: dict[str, Any] | None = None,
        on_people_changed: Callable[[], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.camera_source = camera_source
        self.enrollment_cfg = enrollment_cfg or {}
        self.detection_cfg = detection_cfg or {}
        self.on_people_changed = on_people_changed
        self._people_list = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None)
        self._people_list.bind(minimum_height=self._people_list.setter("height"))
        self._capture_event = None
        self._build_ui()
        self.refresh_people()

    def on_enter(self, *_args) -> None:
        self.refresh_people()

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="vertical", padding=16, spacing=12)

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=48)
        title = Label(text="Face Settings", font_size=24, halign="left", valign="middle")
        title.bind(size=lambda inst, _val: setattr(inst, "text_size", inst.size))
        header.add_widget(title)
        back_hint = Label(
            text="Swipe right",
            size_hint_x=None,
            width=120,
            halign="right",
            valign="middle",
            color=(0.6, 0.6, 0.6, 1),
        )
        back_hint.bind(size=lambda inst, _val: setattr(inst, "text_size", inst.size))
        header.add_widget(back_hint)
        root.add_widget(header)

        actions = BoxLayout(orientation="horizontal", size_hint_y=None, height=48, spacing=8)
        add_button = Button(text="Add Face", size_hint_x=0.5)
        add_button.bind(on_press=lambda _btn: self._prompt_add_face())
        refresh_button = Button(text="Refresh", size_hint_x=0.5)
        refresh_button.bind(on_press=lambda _btn: self.refresh_people())
        actions.add_widget(add_button)
        actions.add_widget(refresh_button)
        root.add_widget(actions)

        self._status_label = Label(
            text="",
            size_hint_y=None,
            height=24,
            color=(0.8, 0.8, 0.8, 1),
        )
        root.add_widget(self._status_label)

        scroll = ScrollView(size_hint=(1, 1))
        scroll.add_widget(self._people_list)
        root.add_widget(scroll)

        self.add_widget(root)

    def refresh_people(self) -> None:
        self._people_list.clear_widgets()
        people = list_people()
        if not people:
            empty = Label(
                text="No faces enrolled yet.\nTap Add Face to register someone.",
                size_hint_y=None,
                height=80,
                halign="center",
                valign="middle",
                color=(0.7, 0.7, 0.7, 1),
            )
            empty.bind(size=lambda inst, _val: setattr(inst, "text_size", inst.size))
            self._people_list.add_widget(empty)
            return

        for person in people:
            self._people_list.add_widget(self._build_person_row(person.get("name", "Unknown")))

    def _build_person_row(self, name: str) -> BoxLayout:
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=52, spacing=8)

        label = Label(
            text=name,
            halign="left",
            valign="middle",
        )
        label.bind(size=lambda inst, _val: setattr(inst, "text_size", inst.size))
        row.add_widget(label)

        edit_button = Button(text="Edit", size_hint_x=None, width=80)
        edit_button.bind(on_press=lambda _btn, person_name=name: self._prompt_edit_face(person_name))
        row.add_widget(edit_button)

        delete_button = Button(text="Delete", size_hint_x=None, width=90)
        delete_button.bind(
            on_press=lambda _btn, person_name=name: self._confirm_delete_face(person_name)
        )
        row.add_widget(delete_button)

        return row

    def _set_status(self, message: str) -> None:
        self._status_label.text = message

    def _notify_changed(self) -> None:
        if self.on_people_changed is not None:
            self.on_people_changed()

    def _person_exists(self, name: str) -> bool:
        lowered = name.strip().lower()
        return any(person.get("name", "").strip().lower() == lowered for person in list_people())

    def _stop_capture(self) -> None:
        if self._capture_event is not None:
            self._capture_event.cancel()
            self._capture_event = None

    def _prompt_add_face(self) -> None:
        if self.camera_source is None:
            self._set_status("Camera is not available for enrollment.")
            return

        content = BoxLayout(orientation="vertical", spacing=8, padding=8)
        name_input = TextInput(hint_text="Name", multiline=False, size_hint_y=None, height=40)
        content.add_widget(name_input)
        content.add_widget(
            Label(
                text="After Save, look at the camera while photos are captured.",
                font_size=12,
                color=(0.7, 0.7, 0.7, 1),
                size_hint_y=None,
                height=36,
            )
        )

        popup = Popup(
            title="Add Face",
            content=content,
            size_hint=(0.85, 0.4),
            auto_dismiss=False,
        )

        actions = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=8)

        def _save(_btn) -> None:
            name = name_input.text.strip()
            if not name:
                self._set_status("Name is required.")
                return
            if self._person_exists(name):
                self._set_status(f"{name} already exists.")
                return

            popup.dismiss()
            self._start_enrollment_capture(name)

        save_button = Button(text="Save")
        save_button.bind(on_press=_save)
        cancel_button = Button(text="Cancel")
        cancel_button.bind(on_press=lambda _btn: popup.dismiss())
        actions.add_widget(save_button)
        actions.add_widget(cancel_button)
        content.add_widget(actions)

        popup.open()
        Clock.schedule_once(lambda _dt: setattr(name_input, "focus", True), 0.1)

    def _start_enrollment_capture(self, name: str) -> None:
        capture_count = int(self.enrollment_cfg.get("capture_count", 5))
        sample_interval = float(self.enrollment_cfg.get("sample_interval_seconds", 0.4))

        content = BoxLayout(orientation="vertical", spacing=8, padding=8)
        progress = Label(
            text="Look at the camera...",
            halign="center",
            valign="middle",
        )
        progress.bind(size=lambda inst, _val: setattr(inst, "text_size", inst.size))
        content.add_widget(progress)

        popup = Popup(
            title=f"Enrolling {name}",
            content=content,
            size_hint=(0.85, 0.35),
            auto_dismiss=False,
        )

        captured_frames: list[Any] = []

        def _cancel(_btn) -> None:
            self._stop_capture()
            popup.dismiss()
            self._set_status("Enrollment cancelled.")

        cancel_button = Button(text="Cancel", size_hint_y=None, height=44)
        cancel_button.bind(on_press=_cancel)
        content.add_widget(cancel_button)

        def _sample(_dt) -> None:
            snapshot = self.camera_source.get_snapshot()
            if snapshot.frame is None:
                progress.text = "Waiting for camera..."
                return

            if len(snapshot.boxes) != 1:
                progress.text = (
                    f"Need exactly one face ({len(snapshot.boxes)} detected). "
                    f"Captured {len(captured_frames)}/{capture_count}..."
                )
                return

            captured_frames.append(snapshot.frame.copy())
            progress.text = f"Capturing {len(captured_frames)}/{capture_count}..."
            if len(captured_frames) >= capture_count:
                self._stop_capture()
                popup.dismiss()
                self._finish_enrollment(name, captured_frames)

        popup.open()
        self._capture_event = Clock.schedule_interval(_sample, sample_interval)

    def _finish_enrollment(self, name: str, frames: list[Any]) -> None:
        self._set_status(f"Saving enrollment for {name}...")
        try:
            result = enroll_from_frames(
                name,
                frames,
                self.enrollment_cfg,
                self.detection_cfg,
            )
        except Exception as exc:
            logger.exception("Enrollment failed for %s", name)
            self._set_status(str(exc))
            return

        self._set_status(
            f"Enrolled {name} ({result['photo_count']} photo(s) saved)."
        )
        self.refresh_people()
        self._notify_changed()

    def _prompt_edit_face(self, current_name: str) -> None:
        content = BoxLayout(orientation="vertical", spacing=8, padding=8)
        name_input = TextInput(
            text=current_name,
            multiline=False,
            size_hint_y=None,
            height=40,
        )
        content.add_widget(name_input)

        popup = Popup(
            title="Edit Face",
            content=content,
            size_hint=(0.85, 0.35),
            auto_dismiss=False,
        )

        actions = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=8)

        def _save(_btn) -> None:
            new_name = name_input.text.strip()
            if not new_name:
                self._set_status("Name is required.")
                return
            try:
                update_person_name(current_name, new_name)
            except PersonNotFoundError:
                self._set_status(f"{current_name} not found.")
                return
            except PersonAlreadyExistsError:
                self._set_status(f"{new_name} already exists.")
                return
            except PeopleStoreError as exc:
                self._set_status(str(exc))
                return

            popup.dismiss()
            self._set_status(f"Renamed {current_name} to {new_name}.")
            self.refresh_people()
            self._notify_changed()

        save_button = Button(text="Save")
        save_button.bind(on_press=_save)
        cancel_button = Button(text="Cancel")
        cancel_button.bind(on_press=lambda _btn: popup.dismiss())
        actions.add_widget(save_button)
        actions.add_widget(cancel_button)
        content.add_widget(actions)

        popup.open()
        Clock.schedule_once(lambda _dt: setattr(name_input, "focus", True), 0.1)

    def _confirm_delete_face(self, name: str) -> None:
        content = BoxLayout(orientation="vertical", spacing=8, padding=8)
        content.add_widget(Label(text=f"Delete {name}?"))

        popup = Popup(
            title="Delete Face",
            content=content,
            size_hint=(0.85, 0.3),
            auto_dismiss=False,
        )

        actions = BoxLayout(orientation="horizontal", size_hint_y=None, height=44, spacing=8)

        def _delete(_btn) -> None:
            try:
                delete_person(name)
            except PersonNotFoundError:
                self._set_status(f"{name} not found.")
                return
            except PeopleStoreError as exc:
                self._set_status(str(exc))
                return

            popup.dismiss()
            self._set_status(f"Deleted {name}.")
            self.refresh_people()
            self._notify_changed()

        delete_button = Button(text="Delete", background_color=(0.7, 0.2, 0.2, 1))
        delete_button.bind(on_press=_delete)
        cancel_button = Button(text="Cancel")
        cancel_button.bind(on_press=lambda _btn: popup.dismiss())
        actions.add_widget(delete_button)
        actions.add_widget(cancel_button)
        content.add_widget(actions)

        popup.open()
