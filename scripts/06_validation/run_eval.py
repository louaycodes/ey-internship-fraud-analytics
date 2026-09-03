import sys
import os
import importlib
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "../../"))

compare_exact = importlib.import_module("scripts.06_validation.compare_exact")
load_data = compare_exact.load_data
evaluate_exact = compare_exact.evaluate_exact

j, t = load_data("data/raw/journal_fraudes_injectees.csv", "output_clean/transactions_scorees.csv")

# Hack evaluate_exact since we don't have Ref/New anymore, we just want to print New
res = evaluate_exact(j, t)
print(res)
