import { describe, expect, it } from "vitest";
import {
  countDiffRows,
  diffFileSlug,
  diffRowId,
  findDiffLine,
  parseUnifiedDiff,
} from "@/lib/diff";

const SAMPLE_DIFF = [
  "diff --git a/app/pipeline.py b/app/pipeline.py",
  "index 111..222 100644",
  "--- a/app/pipeline.py",
  "+++ b/app/pipeline.py",
  "@@ -10,4 +10,6 @@ def run():",
  "     unchanged()",
  "-    old_call()",
  "+    new_call()",
  "+    second_call()",
  "     tail()",
  "diff --git a/app/new_module.py b/app/new_module.py",
  "new file mode 100644",
  "--- /dev/null",
  "+++ b/app/new_module.py",
  "@@ -0,0 +1,2 @@",
  "+from app import pipeline",
  "+VALUE = 1",
  "diff --git a/app/legacy.py b/app/legacy.py",
  "deleted file mode 100644",
  "--- a/app/legacy.py",
  "+++ /dev/null",
  "@@ -1,1 +0,0 @@",
  "-GONE = True",
  "diff --git a/app/old_name.py b/app/new_name.py",
  "similarity index 90%",
  "rename from app/old_name.py",
  "rename to app/new_name.py",
  "--- a/app/old_name.py",
  "+++ b/app/new_name.py",
  "@@ -1,1 +1,1 @@",
  "-before",
  "+after",
].join("\n");

describe("parseUnifiedDiff", () => {
  const files = parseUnifiedDiff(SAMPLE_DIFF);

  it("parses modified files with correct line numbers", () => {
    const pipeline = files.find((file) => file.path === "app/pipeline.py");
    expect(pipeline).toBeDefined();
    expect(pipeline?.hunks).toHaveLength(1);
    const rows = pipeline!.hunks[0].rows;
    expect(rows[0]).toMatchObject({ type: "context", oldNumber: 10, newNumber: 10 });
    expect(rows[1]).toMatchObject({ type: "removed", oldNumber: 11, newNumber: null });
    expect(rows[2]).toMatchObject({ type: "added", oldNumber: null, newNumber: 11 });
    expect(rows[3]).toMatchObject({ type: "added", oldNumber: null, newNumber: 12 });
    expect(rows[4]).toMatchObject({ type: "context", oldNumber: 12, newNumber: 13 });
  });

  it("marks new, deleted, and renamed files", () => {
    const newFile = files.find((file) => file.path === "app/new_module.py");
    expect(newFile?.isNew).toBe(true);
    const deleted = files.find((file) => file.path === "app/legacy.py");
    expect(deleted?.isDeleted).toBe(true);
    expect(deleted?.hunks[0].rows[0]).toMatchObject({
      type: "removed",
      oldNumber: 1,
      newNumber: null,
    });
    const renamed = files.find((file) => file.path === "app/new_name.py");
    expect(renamed?.isRename).toBe(true);
    expect(renamed?.oldPath).toBe("app/old_name.py");
  });

  it("counts added and removed rows", () => {
    expect(countDiffRows(files)).toEqual({ added: 5, removed: 3 });
  });
});

describe("citation → diff lookup", () => {
  const files = parseUnifiedDiff(SAMPLE_DIFF);

  it("resolves an added-line citation to its row id", () => {
    const location = findDiffLine(files, "app/pipeline.py", 11);
    expect(location).not.toBeNull();
    expect(location?.row).toMatchObject({ type: "added", newNumber: 11 });
    expect(location?.id).toBe(diffRowId("app/pipeline.py", 11));
  });

  it("resolves removed-line citations that only exist on the old side", () => {
    const location = findDiffLine(files, "app/pipeline.py", 11);
    expect(location).not.toBeNull();
    const removed = findDiffLine(files, "app/legacy.py", 1);
    expect(removed).not.toBeNull();
    expect(removed?.row.type).toBe("removed");
  });

  it("matches the old path of a renamed file", () => {
    const location = findDiffLine(files, "app/old_name.py", null);
    expect(location?.file.path).toBe("app/new_name.py");
  });

  it("returns null for unknown files", () => {
    expect(findDiffLine(files, "app/missing.py", 1)).toBeNull();
  });
});

describe("diffFileSlug", () => {
  it("is deterministic and DOM-safe", () => {
    const slug = diffFileSlug("app/pipeline.py");
    expect(slug).toBe(diffFileSlug("app/pipeline.py"));
    expect(slug).toMatch(/^[0-9a-z]+-pipeline_py$/);
    expect(diffFileSlug("app/other.py")).not.toBe(slug);
  });
});
