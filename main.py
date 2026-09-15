"""BudgetQuest entry point.

    python main.py
    python main.py path/to/workbook.xlsx path/to/statement.txt
"""

import sys

from budgetquest.app import run

if __name__ == "__main__":
    run(sys.argv[1:])
