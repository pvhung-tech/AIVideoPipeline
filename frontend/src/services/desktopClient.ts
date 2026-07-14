export async function openDesktopPath(path: string): Promise<void> {
  if (!path.trim()) {
    throw new Error("Output path is unavailable.");
  }
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("open_path", { path });
}

export async function selectScriptFile(): Promise<string | null> {
  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({
    directory: false,
    multiple: false,
    filters: [
      {
        name: "Script files",
        extensions: ["txt", "srt"],
      },
    ],
  });

  if (Array.isArray(selected)) {
    return selected[0] ?? null;
  }
  return selected;
}
