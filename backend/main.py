# main.py
#
# Thin entrypoint — exists so the Docker ENTRYPOINT ("python main.py") and all
# existing Cloud Run job definitions continue to work without modification.
# All logic lives in the planning_center_reports package.

from planning_center_reports.cli import main

if __name__ == "__main__":
    main()
