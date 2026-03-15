"""Near-duplicate code block detection — Task 338."""

from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict


@dataclass(frozen=True)
class DuplicateBlock:
    file_a: str
    file_b: str
    lines_a: tuple[int, int]   # (start, end) 1-based inclusive
    lines_b: tuple[int, int]
    size: int                  # number of matching lines


class DuplicateDetector:
    """Detect near-duplicate code blocks across source files.

    Uses a sliding-window hash comparison.  Lines are normalised (stripped)
    before hashing so formatting-only differences are ignored.
    """

    def detect(
        self,
        sources: dict[str, str],
        min_lines: int = 5,
    ) -> list[DuplicateBlock]:
        """Return all duplicate blocks of at least *min_lines* lines.

        Parameters
        ----------
        sources:
            Mapping of ``file_path -> source_code``.
        min_lines:
            Minimum window size to consider a duplicate.
        """
        if not sources or min_lines < 1:
            return []

        # Build normalised line lists per file
        file_lines: dict[str, list[str]] = {
            fp: [ln.strip() for ln in src.splitlines()]
            for fp, src in sources.items()
        }

        # Build window-hash index: hash -> list of (file, start_idx)
        # start_idx is 0-based
        hash_index: dict[int, list[tuple[str, int]]] = defaultdict(list)
        for fp, lines in file_lines.items():
            if len(lines) < min_lines:
                continue
            for i in range(len(lines) - min_lines + 1):
                window = tuple(lines[i : i + min_lines])
                # Skip windows that are all blank
                if all(not ln for ln in window):
                    continue
                h = hash(window)
                hash_index[h].append((fp, i))

        # Find collisions — pairs of (file, start) sharing the same window hash
        results: list[DuplicateBlock] = []
        seen: set[tuple] = set()

        for positions in hash_index.values():
            if len(positions) < 2:
                continue
            for i in range(len(positions)):
                for j in range(i + 1, len(positions)):
                    fp_a, start_a = positions[i]
                    fp_b, start_b = positions[j]
                    # Canonical order to avoid duplicates
                    if (fp_a, start_a) > (fp_b, start_b):
                        fp_a, start_a, fp_b, start_b = fp_b, start_b, fp_a, start_a
                    key = (fp_a, start_a, fp_b, start_b)
                    if key in seen:
                        continue
                    seen.add(key)
                    results.append(
                        DuplicateBlock(
                            file_a=fp_a,
                            file_b=fp_b,
                            lines_a=(start_a + 1, start_a + min_lines),
                            lines_b=(start_b + 1, start_b + min_lines),
                            size=min_lines,
                        )
                    )

        return results
