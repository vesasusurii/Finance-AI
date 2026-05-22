import { useCallback, useState } from "react";

interface FileDropzoneProps {
  onFiles: (files: File[]) => void;
  accept?: string;
}

export function FileDropzone({
  onFiles,
  accept = "application/pdf,image/*",
}: FileDropzoneProps) {
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState<File[]>([]);

  const addFiles = useCallback(
    (list: FileList | null) => {
      if (!list?.length) return;
      const next = [...selected, ...Array.from(list)];
      setSelected(next);
      onFiles(next);
    },
    [selected, onFiles],
  );

  function removeAt(index: number) {
    const next = selected.filter((_, i) => i !== index);
    setSelected(next);
    onFiles(next);
  }

  return (
    <div className="stack-3">
      <div
        className="card"
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles(e.dataTransfer.files);
        }}
        style={{
          borderStyle: "dashed",
          opacity: dragging ? 0.9 : 1,
          textAlign: "center",
          padding: "2rem",
        }}
      >
        <p className="text-fg2">Drag invoice PDFs or images here</p>
        <label className="btn btn-ghost" style={{ marginTop: "1rem" }}>
          Choose files
          <input
            type="file"
            multiple
            accept={accept}
            hidden
            onChange={(e) => addFiles(e.target.files)}
          />
        </label>
      </div>
      {selected.length > 0 && (
        <ul className="stack-2">
          {selected.map((f, i) => (
            <li
              key={`${f.name}-${i}`}
              style={{ display: "flex", justifyContent: "space-between" }}
            >
              <span className="tok">{f.name}</span>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => removeAt(i)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
