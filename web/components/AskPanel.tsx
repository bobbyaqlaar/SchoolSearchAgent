"use client";

import { useEffect, useState } from "react";
import {
  type SchoolRow,
  type TelemetryEntry,
  ask,
  fetchModels,
} from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";

interface AskPanelProps {
  onSchoolResults?: (schools: SchoolRow[]) => void;
}

export function AskPanel({ onSchoolResults }: AskPanelProps): React.ReactElement {
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState<string>("github:gpt-4o-mini");
  const [question, setQuestion] = useState<string>("");
  const [answer, setAnswer] = useState<string>("");
  const [telemetry, setTelemetry] = useState<TelemetryEntry | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    fetchModels()
      .then((ids) => {
        setModels(ids);
        const preferred =
          ids.find((id) => id === "github:gpt-4o-mini") ??
          ids.find((id) => id.startsWith("github:")) ??
          ids[0];
        if (preferred) setModel(preferred);
      })
      .catch(() => setModels([]));
  }, []);

  async function submit(): Promise<void> {
    setLoading(true);
    setError("");
    setAnswer("");
    setTelemetry(null);
    try {
      const env = await ask(question, model);
      setAnswer(env.data.answer);
      onSchoolResults?.(env.data.schools ?? []);
      const entries = Object.values(env.telemetry);
      setTelemetry(entries.length > 0 ? entries[0] : null);
    } catch (err) {
      const message =
        err instanceof Error && err.message
          ? err.message
          : "The assistant is unavailable right now. Please try again later.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section
      aria-labelledby="ask-assistant-heading"
      className="rounded-lg border border-border bg-surface p-4 dark:border-border-dark dark:bg-surface-dark"
    >
      <h2 id="ask-assistant-heading" className="font-semibold">
        Ask the assistant
      </h2>
      <p className="mt-1 text-sm text-muted dark:text-muted-dark">
        Or describe what you need in plain language — results appear in the
        table below.
      </p>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row">
        <Select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          aria-label="Model"
          className="sm:max-w-xs"
        >
          {models.length === 0 && <option value={model}>{model}</option>}
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </Select>
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Outstanding schools under AED 90,000"
          className="flex-1"
          aria-label="Question"
        />
        <Button
          size="sm"
          onClick={submit}
          disabled={loading || !question}
          className="transition-all duration-200 ease-in-out hover:scale-[1.02] active:scale-[0.98]"
        >
          {loading ? "Thinking…" : "Ask"}
        </Button>
      </div>

      {loading && (
        <div className="mt-3 space-y-2" role="status" aria-label="Generating answer">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      )}
      {error && (
        <p className="mt-3 text-sm text-danger dark:text-amber-300">{error}</p>
      )}
      {answer && (
        <p className="mt-3 rounded-md bg-brand/5 p-3 text-sm leading-relaxed dark:bg-brand/10">
          {answer}
        </p>
      )}
      {telemetry && (
        <p className="mt-2 text-xs text-muted dark:text-muted-dark">
          {telemetry.model} · in {telemetry.input_tokens} / out{" "}
          {telemetry.output_tokens} tokens · ${telemetry.cost_usd.toFixed(4)}
        </p>
      )}
    </section>
  );
}
