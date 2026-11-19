"""Create an IFCB project with the NOC folder layout (section 1 of the app).

    python create_project.py <parent folder> --serial 225 --cruise-id ce26008 --name ar7e

Creates <parent folder>/ifcb_sn225_ce26008_ar7e/ with raw, metadata, log, whoi_v4_V131_features,
ecotaxa_import_zip_seastar and figures. If the project already exists, only its missing folders are created:
nothing that is already there is changed. Then copy the day folders (DYYYYMMDD) of the IFCB into raw/.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import project


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("parent", help="folder where the project goes, e.g. Y:\\")
    parser.add_argument("--serial", required=True, help="IFCB serial number, e.g. 225")
    parser.add_argument("--cruise-id", required=True, help="e.g. ce26008")
    parser.add_argument("--name", required=True, help="cruise name, e.g. ar7e")
    args = parser.parse_args()

    try:
        name = project.project_name(args.serial, args.cruise_id, args.name)
    except ValueError as e:
        sys.exit(str(e))
    parent = os.path.abspath(args.parent)
    root = os.path.join(parent, name)
    if os.path.isdir(root):
        created = project.create_missing_dirs(root)
        print(f"{root} already exists: " + (f"created the missing folders {', '.join(created)}." if created
                                             else "it has every folder, nothing changed."))
    else:
        try:
            project.create_project(parent, name)
        except (FileNotFoundError, FileExistsError) as e:
            sys.exit(str(e))
        print(f"Created {root}")
    print(f"Next: copy the day folders (DYYYYMMDD) of the IFCB into {os.path.join(root, 'raw')}, "
          f"then python project_status.py {root}")


if __name__ == "__main__":
    main()
