"use client";

import { type ComponentProps, useState } from "react";
import { ExternalLinkIcon, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  type ElicitationAnswer,
  type ElicitationChoices,
  type ElicitationField,
  type ElicitationInterrupt,
  type ElicitationRequest,
  type ElicitationResponse,
  elicitationChoices,
} from "@/lib/transcript";

type FormValues = Map<string, Map<string, unknown>>;

export function ElicitationForm({
  interrupt,
  interruptId,
  respond,
  disabled = false,
}: {
  interrupt: ElicitationInterrupt;
  interruptId: string;
  respond: (
    response: ElicitationResponse,
    interruptId: string | null,
  ) => Promise<void>;
  disabled?: boolean;
}) {
  const [values, setValues] = useState<FormValues>(
    () =>
      new Map(
        interrupt.requests.map((request) => [
          request.key,
          defaults(request),
        ]),
      ),
  );
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const answer = async (
    build: (request: ElicitationRequest) => ElicitationAnswer,
  ) => {
    if (disabled || submitting || sent) return;
    setSubmitting(true);
    setError(null);
    try {
      await respond(
        {
          responses: Object.fromEntries(
            interrupt.requests.map((request) => [
              request.key,
              build(request),
            ]),
          ),
        },
        interruptId,
      );
      setSent(true);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The response could not be sent.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const off = disabled || submitting || sent;
  const incomplete = interrupt.requests.some((request) =>
    missingAnswers(request, values.get(request.key) ?? new Map()),
  );

  return (
    <form
      className="my-3 space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        void answer((request) =>
          request.mode === "form"
            ? {
                action: "accept",
                content: Object.fromEntries(values.get(request.key) ?? []),
              }
            : { action: "accept" },
        );
      }}
    >
      {interrupt.requests.map((request) => (
        <fieldset key={request.key} disabled={off} className="space-y-2">
          <p className="text-sm">{request.message}</p>
          {request.mode === "url" ? (
            <a
              href={request.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-petrol underline"
            >
              Open link <ExternalLinkIcon className="size-3" />
            </a>
          ) : (
            <div className="max-w-md space-y-4">
              {Object.entries(request.requested_schema.properties ?? {}).map(
                ([name, field], _, all) => (
                  <FieldInput
                    key={name}
                    name={name}
                    field={field}
                    titled={all.length > 1}
                    required={
                      request.requested_schema.required?.includes(name) ?? false
                    }
                    value={values.get(request.key)?.get(name)}
                    onChange={(value) => {
                      setValues((previous) =>
                        new Map(previous).set(
                          request.key,
                          new Map(previous.get(request.key)).set(name, value),
                        ),
                      );
                    }}
                  />
                ),
              )}
            </div>
          )}
        </fieldset>
      ))}
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="submit"
          disabled={off || incomplete}
          className="inline-flex shrink-0 cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md bg-petrol px-3 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting && <Loader2 className="size-3 animate-spin" />}
          {interrupt.requests.every((request) => request.mode === "url")
            ? "Done"
            : "Submit"}
        </button>
        <button
          type="button"
          disabled={off}
          onClick={() => {
            void answer(() => ({ action: "decline" }));
          }}
          className="shrink-0 cursor-pointer whitespace-nowrap rounded-md border border-input bg-card px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:border-border-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          Decline
        </button>
        <button
          type="button"
          disabled={off}
          onClick={() => {
            void answer(() => ({ action: "cancel" }));
          }}
          className="shrink-0 cursor-pointer whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
        >
          Cancel tool
        </button>
      </div>
    </form>
  );
}

function FieldInput({
  name,
  field,
  required,
  titled,
  value,
  onChange,
}: {
  name: string;
  field: ElicitationField;
  required: boolean;
  titled: boolean;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const title = field.title ?? name;
  const choices = elicitationChoices(field);
  if (choices) {
    const chips = (
      <ChoiceChips
        label={title}
        choices={choices}
        value={value}
        onChange={onChange}
        max={field.maxItems}
      />
    );
    return titled ? (
      <div className="space-y-1.5">
        <p className="text-xs font-medium text-muted-foreground">{title}</p>
        {chips}
      </div>
    ) : (
      chips
    );
  }
  if (field.type === "boolean") {
    return (
      <div className="space-y-1.5">
        {titled && (
          <p className="text-xs font-medium text-muted-foreground">{title}</p>
        )}
        <div className="grid grid-cols-2 gap-1.5" role="radiogroup" aria-label={title}>
          <Chip
            on={value === true}
            role="radio"
            aria-checked={value === true}
            onClick={() => {
              onChange(true);
            }}
          >
            Yes
          </Chip>
          <Chip
            on={value === false}
            role="radio"
            aria-checked={value === false}
            onClick={() => {
              onChange(false);
            }}
          >
            No
          </Chip>
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-1.5">
      {titled && (
        <label
          htmlFor={`elicitation-${name}`}
          className="text-xs font-medium text-muted-foreground"
        >
          {title}
        </label>
      )}
      <Input
        id={`elicitation-${name}`}
        aria-label={title}
        placeholder={title}
        required={required}
        type={inputType(field)}
        step={
          field.type === "integer"
            ? 1
            : field.type === "number"
              ? "any"
              : undefined
        }
        value={
          typeof value === "string" || typeof value === "number" ? value : ""
        }
        onChange={(event) => {
          const raw = event.target.value;
          const numeric =
            field.type === "number" || field.type === "integer";
          onChange(numeric && raw !== "" ? Number(raw) : raw);
        }}
      />
      {field.description && (
        <p className="text-xs text-muted-foreground">{field.description}</p>
      )}
    </div>
  );
}

function Chip({
  on,
  className,
  ...props
}: ComponentProps<"button"> & { on: boolean }) {
  return (
    <button
      type="button"
      className={cn(
        "w-full cursor-pointer rounded-md border px-3 py-2 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        on
          ? "border-petrol bg-petrol text-white"
          : "border-input bg-card text-foreground hover:border-border-hover",
        className,
      )}
      {...props}
    />
  );
}

function ChoiceChips({
  label,
  choices,
  value,
  onChange,
  max,
}: {
  label: string;
  choices: ElicitationChoices;
  value: unknown;
  onChange: (value: unknown) => void;
  max?: number;
}) {
  const picked = choices.multi
    ? Array.isArray(value)
      ? (value as string[])
      : []
    : typeof value === "string"
      ? [value]
      : [];
  const full = max != null && picked.length >= max;
  return (
    <div
      role={choices.multi ? "group" : "radiogroup"}
      aria-label={label}
      className="flex flex-col gap-1.5"
    >
      {choices.options.map((option) => {
        const on = picked.includes(option.value);
        return (
          <Chip
            key={option.value}
            on={on}
            role={choices.multi ? undefined : "radio"}
            aria-checked={choices.multi ? undefined : on}
            aria-pressed={choices.multi ? on : undefined}
            disabled={!on && choices.multi && full}
            onClick={() => {
              if (!choices.multi) {
                onChange(option.value);
              } else {
                onChange(
                  on
                    ? picked.filter((item) => item !== option.value)
                    : [...picked, option.value],
                );
              }
            }}
          >
            {option.label}
          </Chip>
        );
      })}
    </div>
  );
}

function missingAnswers(
  request: ElicitationRequest,
  answers: Map<string, unknown>,
) {
  if (request.mode !== "form") return false;
  const { properties = {}, required = [] } = request.requested_schema;
  return Object.entries(properties).some(([name, field]) => {
    const value = answers.get(name);
    if (field.type === "boolean") {
      return required.includes(name) && value === undefined;
    }
    const choices = elicitationChoices(field);
    if (!choices) {
      return (
        required.includes(name) &&
        (value === undefined || value === null || value === "")
      );
    }
    const count = Array.isArray(value) ? value.length : value ? 1 : 0;
    const minimum = field.minItems ?? (required.includes(name) ? 1 : 0);
    return count < minimum;
  });
}

function inputType(field: ElicitationField): string {
  if (field.type === "number" || field.type === "integer") return "number";
  if (field.format === "date") return "date";
  if (field.format === "email") return "email";
  if (field.format === "uri") return "url";
  return "text";
}

function defaults(request: ElicitationRequest): Map<string, unknown> {
  if (request.mode !== "form") return new Map();
  return new Map(
    Object.entries(request.requested_schema.properties ?? {})
      .filter(([, field]) => field.default !== undefined)
      .map(([name, field]) => [name, field.default]),
  );
}
