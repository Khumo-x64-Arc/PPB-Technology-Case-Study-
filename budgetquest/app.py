"""The application shell.

Owns the window, the navigation rail and the view stack. It knows nothing
about budgets, merchants or fraud -- it just loops over `views.VIEWS`.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from . import theme
from .engine import Insights, analyse
from .formatting import rand
from .sources import load_statement
from .views import VIEWS, View

APP_NAME = "BudgetQuest"
TAGLINE = "Rule-based money coaching"


class BudgetQuestApp(ctk.CTk):
    def __init__(self, insights: Insights):
        super().__init__()
        self.insights = insights
        self._views: dict[str, View] = {}
        self._buttons: dict[str, ctk.CTkButton] = {}
        self.active: str | None = None

        self.title(f"{APP_NAME} — {insights.statement.account.account_name}")
        self.geometry("1320x820")
        self.minsize(1150, 700)
        self.configure(fg_color=theme.WASH)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_rail()
        self.container = ctk.CTkFrame(self, fg_color=theme.WASH, corner_radius=0)
        self.container.grid(row=0, column=1, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.show(VIEWS[0].name)

    # -- navigation --------------------------------------------------------
    def _build_rail(self) -> None:
        rail = ctk.CTkFrame(self, width=232, corner_radius=0, fg_color=theme.NAVY)
        rail.grid(row=0, column=0, sticky="nsw")
        rail.grid_propagate(False)

        header = ctk.CTkFrame(rail, fg_color="transparent")
        header.pack(fill="x", padx=22, pady=(26, 22))
        ctk.CTkLabel(header, text=APP_NAME, font=theme.font(22, "bold"),
                     text_color=theme.WHITE, anchor="w").pack(fill="x")
        ctk.CTkLabel(header, text=TAGLINE, font=theme.font(theme.CAPTION),
                     text_color=theme.PALE_INK, anchor="w").pack(fill="x")

        for view_class in VIEWS:
            button = ctk.CTkButton(
                rail, text=view_class.name, anchor="w", height=40, corner_radius=8,
                font=theme.font(theme.BODY), fg_color="transparent",
                hover_color=theme.NAVY_SOFT, text_color=theme.PALE_INK,
                command=lambda name=view_class.name: self.show(name))
            button.pack(fill="x", padx=14, pady=2)
            self._buttons[view_class.name] = button

        footer = ctk.CTkFrame(rail, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=22, pady=20)
        account = self.insights.statement.account
        period = (f"{account.period_from.strftime('%d %b')} to "
                  f"{account.period_to.strftime('%d %b %Y')}")
        for line, colour in ((account.account_id, theme.PALE_INK),
                             (period, theme.PALE_INK),
                             (f"Closing {rand(account.closing_balance)}",
                              theme.WHITE)):
            ctk.CTkLabel(footer, text=line, font=theme.font(theme.CAPTION),
                         text_color=colour, anchor="w").pack(fill="x")
        ctk.CTkLabel(footer, text="Reading the JSON statement. Rule-based only, no AI analytics.",
                     font=theme.font(theme.CAPTION), text_color=theme.FOOTNOTE,
                     anchor="w", wraplength=190, justify="left").pack(fill="x",
                                                                      pady=(8, 0))

    def show(self, name: str) -> None:
        if name == self.active:
            return
        if name not in self._views:                       # build on first visit
            view_class = next(item for item in VIEWS if item.name == name)
            view = view_class(self.container, self.insights)
            view.grid(row=0, column=0, sticky="nsew")
            self._views[name] = view

        for key, button in self._buttons.items():
            chosen = key == name
            button.configure(fg_color=theme.BLUE if chosen else "transparent",
                             text_color=theme.WHITE if chosen else theme.PALE_INK,
                             font=theme.font(theme.BODY, "bold" if chosen else "normal"))
        self._views[name].tkraise()
        self.active = name


#: The JSON statement is the working source. The Excel reader is still
#: registered in sources.SOURCE_REGISTRY, so passing a workbook path on the
#: command line works without any code change.
DEFAULT_DATA_FILE = "Transaction_DP.txt"


def default_data_files() -> list[Path]:
    folder = Path(__file__).resolve().parent.parent / "data"
    path = folder / DEFAULT_DATA_FILE
    return [path] if path.exists() else []


def run(paths=None) -> None:
    paths = [Path(item) for item in paths] if paths else default_data_files()
    if not paths:
        raise SystemExit(f"No statement found. Put {DEFAULT_DATA_FILE} in the "
                         "'data' folder, or pass a file path on the command line.")

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    BudgetQuestApp(analyse(load_statement(paths))).mainloop()
