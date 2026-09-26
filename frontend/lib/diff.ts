/**
 * Minimal unified-diff parser used to render diffs and link evidence
 * citations to exact diff lines. Handles git-style headers, new/deleted/
 * renamed files, hunks with and without counts, and binary markers.
 */

export interface DiffRow {
  type: "context" | "added" | "removed";
  oldNumber: number | null;
  newNumber: number | null;
  content: string;
}

export interface DiffHunk {
  header: string;
  rows: DiffRow[];
}

export interface DiffFile {
  /** Target (new) path, or the old path for deleted files. */
  path: string;
  oldPath: string;
  isNew: boolean;
  isDeleted: boolean;
  isRename: boolean;
  isBinary: boolean;
  hunks: DiffHunk[];
}

function stripPrefix(path: string): string {
  if (path === "/dev/null") return path;
  return path.replace(/^[ab]\//, "");
}

function cleanHeaderPath(value: string): string {
  // Values look like `a/src/app.py`, `b/src/app.py`, or `/dev/null`; git may
  // also quote paths containing special characters.
  let path = value.trim();
  if (path.startsWith('"') && path.endsWith('"') && path.length >= 2) {
    try {
      path = JSON.parse(path) as string;
    } catch {
      path = path.slice(1, -1);
    }
  }
  path = path.replace(/\t\d+.*$/, ""); // GNU diff trailing line counts
  return path;
}

export function parseUnifiedDiff(diff: string): DiffFile[] {
  const files: DiffFile[] = [];
  let current: DiffFile | null = null;
  let currentHunk: DiffHunk | null = null;
  let oldLine = 0;
  let newLine = 0;

  const lines = diff.split("\n");
  for (const line of lines) {
    if (line.startsWith("diff --git ")) {
      current = {
        path: "",
        oldPath: "",
        isNew: false,
        isDeleted: false,
        isRename: false,
        isBinary: false,
        hunks: [],
      };
      currentHunk = null;
      files.push(current);
      continue;
    }
    if (current === null) continue;

    if (line.startsWith("rename from ")) {
      current.oldPath = stripPrefix(line.slice("rename from ".length));
      current.isRename = true;
    } else if (line.startsWith("rename to ")) {
      current.path = stripPrefix(line.slice("rename to ".length));
    } else if (line.startsWith("--- ")) {
      current.oldPath = stripPrefix(cleanHeaderPath(line.slice(4)));
    } else if (line.startsWith("+++ ")) {
      const newPath = stripPrefix(cleanHeaderPath(line.slice(4)));
      if (!current.path || current.path === "/dev/null") {
        current.path = newPath === "/dev/null" ? current.oldPath : newPath;
      }
      if (current.oldPath === "/dev/null") current.isNew = true;
      if (newPath === "/dev/null") current.isDeleted = true;
      if (!current.oldPath) current.oldPath = current.path;
    } else if (line.startsWith("Binary files ") || line.startsWith("GIT binary patch")) {
      current.isBinary = true;
      currentHunk = null;
    } else if (line.startsWith("@@")) {
      const match = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/.exec(line);
      const oldStart = match ? Number(match[1]) : 0;
      const newStart = match ? Number(match[2]) : 0;
      currentHunk = { header: line, rows: [] };
      current.hunks.push(currentHunk);
      oldLine = oldStart;
      newLine = newStart;
    } else if (currentHunk !== null) {
      if (line.startsWith("+")) {
        currentHunk.rows.push({
          type: "added",
          oldNumber: null,
          newNumber: newLine++,
          content: line.slice(1),
        });
      } else if (line.startsWith("-")) {
        currentHunk.rows.push({
          type: "removed",
          oldNumber: oldLine++,
          newNumber: null,
          content: line.slice(1),
        });
      } else if (line.startsWith(" ") || line === "") {
        currentHunk.rows.push({
          type: "context",
          oldNumber: oldLine++,
          newNumber: newLine++,
          content: line.startsWith(" ") ? line.slice(1) : "",
        });
      } else if (line.startsWith("\\")) {
        // "\ No newline at end of file" — no line-number effect.
      } else {
        currentHunk = null; // unrecognised trailer: stop consuming rows
      }
    }
  }

  for (const file of files) {
    if (!file.path) file.path = file.oldPath;
    if (!file.oldPath) file.oldPath = file.path;
  }
  return files.filter((file) => file.path && file.path !== "/dev/null");
}

/** Stable short DOM id for a file path inside the diff view. */
export function diffFileSlug(path: string): string {
  let hash = 5381;
  for (let index = 0; index < path.length; index += 1) {
    hash = ((hash << 5) + hash + path.charCodeAt(index)) | 0;
  }
  const base = path.split("/").pop() ?? path;
  const safe = base.replace(/[^a-zA-Z0-9_-]+/g, "_").slice(0, 40) || "file";
  return `${(hash >>> 0).toString(36)}-${safe}`;
}

export function diffRowId(path: string, lineNumber: number): string {
  return `diff-${diffFileSlug(path)}-L${lineNumber}`;
}

export interface DiffLocation {
  file: DiffFile;
  row: DiffRow;
  id: string;
}

/**
 * Resolve a backend citation (file path + new-side line number) to a row in
 * the parsed diff. Coverage-gap and added-line citations both use new-side
 * line numbers; dependency citations may omit them.
 */
export function findDiffLine(
  files: DiffFile[],
  filePath: string,
  lineNumber: number | null,
): DiffLocation | null {
  const file = files.find(
    (candidate) => candidate.path === filePath || candidate.oldPath === filePath,
  );
  if (!file) return null;
  if (lineNumber === null) {
    return { file, row: file.hunks[0]?.rows[0] ?? { type: "context", oldNumber: null, newNumber: null, content: "" }, id: `diff-${diffFileSlug(file.path)}` };
  }
  // New-side numbers win (added/context rows); only fall back to old-side
  // numbers for citations that point at removed lines.
  for (const hunk of file.hunks) {
    for (const row of hunk.rows) {
      if (row.newNumber === lineNumber) {
        return { file, row, id: diffRowId(file.path, row.newNumber ?? lineNumber) };
      }
    }
  }
  for (const hunk of file.hunks) {
    for (const row of hunk.rows) {
      if (row.newNumber === null && row.oldNumber === lineNumber) {
        return { file, row, id: diffRowId(file.path, row.oldNumber ?? lineNumber) };
      }
    }
  }
  return null;
}

export interface DiffCounts {
  added: number;
  removed: number;
}

export function countDiffRows(files: DiffFile[]): DiffCounts {
  let added = 0;
  let removed = 0;
  for (const file of files) {
    for (const hunk of file.hunks) {
      for (const row of hunk.rows) {
        if (row.type === "added") added += 1;
        else if (row.type === "removed") removed += 1;
      }
    }
  }
  return { added, removed };
}
