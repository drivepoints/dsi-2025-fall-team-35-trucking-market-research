#!/usr/bin/env python3
import asyncio
import csv
import json
from pathlib import Path
from typing import List, Tuple, Optional

import aiohttp
from aiohttp import ClientSession, ClientError
from tqdm import tqdm

import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FMCSA_DEVELOPER_API_KEY")

if not API_KEY:
    raise ValueError("Missing FMCSA_DEVELOPER_API_KEY in .env file.")

INPUT_PATH = Path("../data/nov_5_census.csv")
OUTPUT_PATH = Path("../data/dot_cargo_carried.csv")
CHECKPOINT_PATH = Path("../data/dot_cargo_carried_checkpoint.json")

# ---- Tuning knobs ----
MAX_CONCURRENCY = 20          # adjust slowly upwards if API tolerates it
BATCH_SIZE = 2000             # number of DOTs per async batch
CHECKPOINT_EVERY = 5000     # write checkpoint after this many new rows


def load_dot_numbers(csv_path: Path) -> List[str]:
    """
    Load DOT numbers from a CSV file.
    Assumes there is a column named 'dot_number'.
    """
    dot_numbers: List[str] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "DOT_NUMBER" not in reader.fieldnames:
            raise ValueError("CSV must contain a 'DOT_NUMBER' column.")
        for row in reader:
            dot_numbers.append(str(row["DOT_NUMBER"]).strip())
    return dot_numbers


def load_checkpoint() -> int:
    """
    Load the last processed index from the checkpoint file.
    Returns the starting index (0 if no checkpoint).
    """
    if not CHECKPOINT_PATH.exists():
        return 0
    try:
        with CHECKPOINT_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        start_index = int(data.get("start_index", 0))
        return max(start_index, 0)
    except Exception:
        # If checkpoint is corrupted, start from 0 (you can tighten this if you want)
        return 0


def save_checkpoint(start_index: int) -> None:
    """
    Save the last processed index to the checkpoint file.
    """
    tmp_path = CHECKPOINT_PATH.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump({"start_index": start_index}, f)
    tmp_path.replace(CHECKPOINT_PATH)


async def fetch_cargo_for_dot(
    session: ClientSession,
    dot_number: str,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Tuple[str, Optional[str]]:
    """
    Fetch cargoCarried info for a single DOT from the FMCSA API.

    Returns (dot_number, cargo_carried or None).
    """
    url = (
        f"https://mobile.fmcsa.dot.gov/qc/services/carriers/"
        f"{dot_number}/cargo-carried?webKey={API_KEY}"
    )

    for attempt in range(max_retries):
        async with semaphore:
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        cargo = None

                        content = data.get("content", [])
                        if isinstance(content, list):
                            cargos = [
                                item.get("cargoClassDesc")
                                for item in content
                                if isinstance(item, dict) and item.get("cargoClassDesc")
                            ]
                            if cargos:
                                cargo = ", ".join(cargos)

                        return dot_number, cargo
                    elif resp.status in (429, 500, 502, 503, 504):
                        # Retryable errors with backoff
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        # Non-retryable error, just return None
                        return dot_number, None
            except (asyncio.TimeoutError, ClientError):
                # Retry on network issues
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

    # If all retries fail:
    return dot_number, None


async def process_batch(
    session: ClientSession,
    dots: List[str],
    semaphore: asyncio.Semaphore,
) -> List[Tuple[str, Optional[str]]]:
    """
    Process a batch of DOT numbers concurrently.
    """
    tasks = [
        asyncio.create_task(fetch_cargo_for_dot(session, dot, semaphore))
        for dot in dots
    ]
    results: List[Tuple[str, Optional[str]]] = await asyncio.gather(*tasks)
    return results


async def main_async():
    # ---- Load DOTs and checkpoint ----
    print(f"Loading DOT numbers from {INPUT_PATH} ...")
    all_dots = load_dot_numbers(INPUT_PATH)
    total_dots = len(all_dots)
    print(f"Total DOT numbers found: {total_dots:,}")

    start_index = load_checkpoint()
    if start_index >= total_dots:
        print("Checkpoint indicates work is already complete.")
        return

    remaining_dots = all_dots[start_index:start_index + 1000]
    remaining_total = len(remaining_dots)
    print(f"Resuming from index {start_index} (remaining: {remaining_total:,})")

    # ---- Open output file in append mode ----
    file_exists = OUTPUT_PATH.exists() and start_index > 0
    with OUTPUT_PATH.open("a", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        if not file_exists:
            # New file or starting from scratch: write header
            writer.writerow(["dot_number", "cargo_carried"])

        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

        # tqdm progress bar
        pbar = tqdm(total=remaining_total, desc="Fetching cargo_carried", unit="dot")

        processed_since_checkpoint = 0
        current_index = start_index

        async with aiohttp.ClientSession() as session:
            # Process in batches to avoid huge memory usage
            for batch_start in range(0, remaining_total, BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, remaining_total)
                batch_dots = remaining_dots[batch_start:batch_end]

                results = await process_batch(session, batch_dots, semaphore)

                # Write batch to CSV and update progress
                for dot, cargo in results:
                    writer.writerow([dot, cargo if cargo else ""])
                    processed_since_checkpoint += 1
                    current_index += 1

                outfile.flush()
                pbar.update(len(batch_dots))

                # Periodic checkpointing
                if processed_since_checkpoint >= CHECKPOINT_EVERY:
                    save_checkpoint(current_index)
                    processed_since_checkpoint = 0

            # Final checkpoint at the end
            save_checkpoint(current_index)
            pbar.close()

    print("Done! Output saved to:", OUTPUT_PATH)
    print("Checkpoint saved to:", CHECKPOINT_PATH)


if __name__ == "__main__":
    asyncio.run(main_async())


