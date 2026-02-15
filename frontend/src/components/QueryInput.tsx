import { useState } from "react";
import { Search } from "lucide-react";

type QueryInputProps = {
  onSubmit: (query: string) => void;
  disabled: boolean;
};

export function QueryInput({ onSubmit, disabled }: QueryInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (trimmed && !disabled) {
      onSubmit(trimmed);
    }
  };

  return (
    <form className="agent-query-bar" onSubmit={handleSubmit}>
      <input
        className="agent-query-input"
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="DESCRIBE WHAT TO FIND..."
        disabled={disabled}
      />
      <button
        className="agent-query-submit"
        type="submit"
        disabled={disabled || !value.trim()}
      >
        <Search size={16} strokeWidth={2.5} style={{ marginRight: 6, verticalAlign: "middle" }} />
        SEARCH
      </button>
    </form>
  );
}
