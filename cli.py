#!/usr/bin/env python3
"""Command-line interface for the MS-DRG Grouper."""

import argparse
import csv
import sys
from pathlib import Path

from drg_grouper.data.models import Encounter, DischargeStatus
from drg_grouper.grouper import create_grouper


def parse_args():
    parser = argparse.ArgumentParser(
        description="MS-DRG Grouper - Assign DRGs to patient encounters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single encounter
  python cli.py --data-dir ./msdrgv43.0icd10_r0_definitionsmanual_text \\
                --pdx I2510 --sdx E119,I10 --age 65 --sex M

  # With procedures
  python cli.py --data-dir ./msdrgv43.0icd10_r0_definitionsmanual_text \\
                --pdx I2510 --proc 02703ZZ --age 65 --sex M

  # Batch processing
  python cli.py --data-dir ./msdrgv43.0icd10_r0_definitionsmanual_text \\
                --input encounters.csv --output results.csv
        """
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Path to CMS definitions manual text files directory"
    )

    # Single encounter options
    parser.add_argument(
        "--pdx",
        type=str,
        help="Principal diagnosis (ICD-10-CM code)"
    )
    parser.add_argument(
        "--sdx",
        type=str,
        help="Secondary diagnoses (comma-separated ICD-10-CM codes)"
    )
    parser.add_argument(
        "--proc",
        type=str,
        help="Procedure codes (comma-separated ICD-10-PCS codes)"
    )
    parser.add_argument(
        "--age",
        type=int,
        default=0,
        help="Patient age in years"
    )
    parser.add_argument(
        "--sex",
        type=str,
        default="U",
        choices=["M", "F", "U"],
        help="Patient sex (M=Male, F=Female, U=Unknown)"
    )
    parser.add_argument(
        "--discharge",
        type=str,
        default="alive",
        choices=["alive", "expired", "transferred"],
        help="Discharge status"
    )

    # Batch processing options
    parser.add_argument(
        "--input",
        type=str,
        help="Input CSV file for batch processing"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output CSV file for batch results"
    )

    # Output options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed grouping notes"
    )

    return parser.parse_args()


def process_single(grouper, args):
    """Process a single encounter from command-line arguments."""
    if not args.pdx:
        print("Error: --pdx (principal diagnosis) is required for single encounter")
        sys.exit(1)

    # Parse secondary diagnoses
    secondary_dx = []
    if args.sdx:
        secondary_dx = [dx.strip() for dx in args.sdx.split(",") if dx.strip()]

    # Parse procedures
    procedures = []
    if args.proc:
        procedures = [p.strip() for p in args.proc.split(",") if p.strip()]

    # Create encounter
    discharge_map = {
        "alive": DischargeStatus.ALIVE,
        "expired": DischargeStatus.EXPIRED,
        "transferred": DischargeStatus.TRANSFERRED
    }

    encounter = Encounter(
        principal_dx=args.pdx,
        secondary_dx=secondary_dx,
        procedures=procedures,
        age=args.age,
        sex=args.sex,
        discharge_status=discharge_map.get(args.discharge, DischargeStatus.ALIVE)
    )

    # Group
    result = grouper.group(encounter)

    # Output
    print("\n" + "=" * 60)
    print("MS-DRG GROUPING RESULT")
    print("=" * 60)
    print(f"DRG:         {result.drg}")
    print(f"Description: {result.description}")
    print(f"MDC:         {result.mdc or 'Pre-MDC'}")
    print(f"Type:        {'Surgical' if result.drg_type.value == 'P' else 'Medical'}")

    if result.mcc_dx:
        print(f"MCC:         {result.mcc_dx}")
    elif result.cc_dx:
        print(f"CC:          {result.cc_dx}")
    else:
        print("CC/MCC:      None")

    if result.surgical_procedure:
        print(f"Primary Procedure: {result.surgical_procedure}")

    if args.verbose and result.grouping_notes:
        print("\nGrouping Notes:")
        for note in result.grouping_notes:
            print(f"  - {note}")

    print("=" * 60 + "\n")


def process_batch(grouper, input_file, output_file, verbose):
    """Process multiple encounters from a CSV file."""
    results = []

    with open(input_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            # Parse row into encounter
            secondary_dx = []
            if row.get('secondary_dx'):
                secondary_dx = [dx.strip() for dx in row['secondary_dx'].split(";")]

            procedures = []
            if row.get('procedures'):
                procedures = [p.strip() for p in row['procedures'].split(";")]

            discharge_map = {
                "alive": DischargeStatus.ALIVE,
                "expired": DischargeStatus.EXPIRED,
                "transferred": DischargeStatus.TRANSFERRED
            }

            encounter = Encounter(
                principal_dx=row.get('principal_dx', ''),
                secondary_dx=secondary_dx,
                procedures=procedures,
                age=int(row.get('age', 0)),
                sex=row.get('sex', 'U'),
                discharge_status=discharge_map.get(
                    row.get('discharge_status', 'alive'),
                    DischargeStatus.ALIVE
                )
            )

            result = grouper.group(encounter)

            results.append({
                'encounter_id': row.get('encounter_id', ''),
                'principal_dx': encounter.principal_dx,
                'drg': result.drg,
                'mdc': result.mdc or '',
                'description': result.description,
                'type': 'Surgical' if result.drg_type.value == 'P' else 'Medical',
                'mcc_dx': result.mcc_dx or '',
                'cc_dx': result.cc_dx or '',
                'notes': '; '.join(result.grouping_notes) if verbose else ''
            })

    # Write results
    if output_file:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['encounter_id', 'principal_dx', 'drg', 'mdc',
                          'description', 'type', 'mcc_dx', 'cc_dx', 'notes']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"Results written to {output_file}")
    else:
        # Print to stdout
        for r in results:
            print(f"{r['encounter_id']}: DRG {r['drg']} - {r['description']}")

    print(f"\nProcessed {len(results)} encounters")


def main():
    args = parse_args()

    # Validate data directory
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: Data directory not found: {data_dir}")
        sys.exit(1)

    print("Initializing MS-DRG Grouper...")
    grouper = create_grouper(data_dir)
    print("Ready.\n")

    if args.input:
        # Batch processing
        process_batch(grouper, args.input, args.output, args.verbose)
    elif args.pdx:
        # Single encounter
        process_single(grouper, args)
    else:
        print("Error: Either --pdx or --input is required")
        print("Use --help for usage information")
        sys.exit(1)


if __name__ == "__main__":
    main()
