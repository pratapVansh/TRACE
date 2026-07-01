import type { SupportedFileType } from "@/types/knowledge";

type SupportedFileTypesProps = {
  fileTypes: SupportedFileType[];
};

export function SupportedFileTypes({ fileTypes }: SupportedFileTypesProps) {
  return (
    <div className="industrial-card p-5 sm:p-6">
      <p className="section-label">Accepted formats</p>
      <h3 className="mt-2 text-lg font-semibold text-white">Supported file types</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        Upload technical records in standard industrial document formats.
      </p>

      <ul className="mt-5 grid gap-3 sm:grid-cols-2">
        {fileTypes.map((fileType) => (
          <li
            key={fileType.extension}
            className="flex items-center justify-between rounded-xl border border-border bg-[var(--surface-secondary)] px-4 py-3"
          >
            <div>
              <p className="text-sm font-medium text-white">
                .{fileType.extension.toUpperCase()}
              </p>
              <p className="text-xs text-muted-foreground">{fileType.label}</p>
            </div>
            <span className="text-xs text-[var(--accent-steel-muted)]">
              Max {fileType.maxSizeMb} MB
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
