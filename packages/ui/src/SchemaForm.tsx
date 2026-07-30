import { useId, useMemo, useState, type FormEvent } from 'react';
import type { JsonSchemaObject, JsonSchemaProperty } from '@modumesh/shared-types';
import { Button } from './Button';

export type SchemaFormErrors = Record<string, string>;

export interface SchemaFormProps {
  schema: JsonSchemaObject;
  value: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
  onSubmit?: (value: Record<string, unknown>) => void;
  submitLabel?: string;
  disabled?: boolean;
  /** External errors (e.g. API validation). Merged with client-side errors on submit. */
  errors?: SchemaFormErrors;
  className?: string;
  idPrefix?: string;
}

function unitOf(prop: JsonSchemaProperty): string | undefined {
  return prop['x-unit'] || prop.unit;
}

function propType(prop: JsonSchemaProperty): string {
  const t = prop.type;
  if (Array.isArray(t)) return t[0] ?? 'string';
  return t ?? (prop.enum ? typeof prop.enum[0] : 'string');
}

export function defaultsFromSchema(schema: JsonSchemaObject): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  const props = schema.properties ?? {};
  for (const [key, prop] of Object.entries(props)) {
    if (prop.default !== undefined) {
      out[key] = prop.default;
      continue;
    }
    if (prop.enum && prop.enum.length > 0) {
      out[key] = prop.enum[0];
      continue;
    }
    const t = propType(prop);
    if (t === 'boolean') out[key] = false;
    else if (t === 'number' || t === 'integer') out[key] = prop.minimum ?? 0;
    else if (t === 'string') out[key] = '';
  }
  return out;
}

export function validateAgainstSchema(
  schema: JsonSchemaObject,
  value: Record<string, unknown>,
): SchemaFormErrors {
  const errors: SchemaFormErrors = {};
  const props = schema.properties ?? {};
  const required = new Set(schema.required ?? []);

  for (const [key, prop] of Object.entries(props)) {
    const raw = value[key];
    const label = prop.title || key;
    const missing =
      raw === undefined ||
      raw === null ||
      (typeof raw === 'string' && raw.trim() === '' && propType(prop) === 'string');

    if (required.has(key) && missing) {
      errors[key] = `${label} is required.`;
      continue;
    }
    if (missing) continue;

    const t = propType(prop);
    if (prop.enum && !prop.enum.includes(raw as never)) {
      errors[key] = `${label} must be one of: ${prop.enum.join(', ')}.`;
      continue;
    }

    if (t === 'string' && typeof raw === 'string') {
      if (prop.minLength != null && raw.length < prop.minLength) {
        errors[key] = `${label} must be at least ${prop.minLength} characters.`;
      } else if (prop.maxLength != null && raw.length > prop.maxLength) {
        errors[key] = `${label} must be at most ${prop.maxLength} characters.`;
      } else if (prop.pattern) {
        try {
          if (!new RegExp(prop.pattern).test(raw)) {
            errors[key] = `${label} has an invalid format.`;
          }
        } catch {
          /* ignore bad patterns */
        }
      }
    }

    if ((t === 'number' || t === 'integer') && typeof raw === 'number') {
      if (t === 'integer' && !Number.isInteger(raw)) {
        errors[key] = `${label} must be a whole number.`;
      } else if (prop.minimum != null && raw < prop.minimum) {
        errors[key] =
          `${label} must be at least ${prop.minimum}${unitOf(prop) ? ` ${unitOf(prop)}` : ''}.`;
      } else if (prop.maximum != null && raw > prop.maximum) {
        errors[key] =
          `${label} must be at most ${prop.maximum}${unitOf(prop) ? ` ${unitOf(prop)}` : ''}.`;
      } else if (prop.exclusiveMinimum != null && raw <= prop.exclusiveMinimum) {
        errors[key] = `${label} must be greater than ${prop.exclusiveMinimum}.`;
      } else if (prop.exclusiveMaximum != null && raw >= prop.exclusiveMaximum) {
        errors[key] = `${label} must be less than ${prop.exclusiveMaximum}.`;
      }
    }

    if (t === 'boolean' && typeof raw !== 'boolean') {
      errors[key] = `${label} must be true or false.`;
    }
  }

  return errors;
}

function FieldHelp({ id, text }: { id: string; text?: string }) {
  if (!text) return null;
  return (
    <p id={id} className="mm-field__help">
      {text}
    </p>
  );
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="mm-field__error" role="alert">
      {message}
    </p>
  );
}

export function SchemaForm({
  schema,
  value,
  onChange,
  onSubmit,
  submitLabel = 'Generate',
  disabled = false,
  errors: externalErrors,
  className = '',
  idPrefix = 'schema',
}: SchemaFormProps) {
  const formId = useId();
  const [touchedSubmit, setTouchedSubmit] = useState(false);
  const clientErrors = useMemo(
    () => (touchedSubmit ? validateAgainstSchema(schema, value) : {}),
    [touchedSubmit, schema, value],
  );
  const errors = { ...clientErrors, ...(externalErrors ?? {}) };
  const props = schema.properties ?? {};
  const required = new Set(schema.required ?? []);

  const setField = (key: string, next: unknown) => {
    onChange({ ...value, [key]: next });
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    setTouchedSubmit(true);
    const nextErrors = validateAgainstSchema(schema, value);
    if (Object.keys(nextErrors).length > 0) return;
    onSubmit?.(value);
  };

  return (
    <form
      className={`mm-schema-form ${className}`.trim()}
      onSubmit={handleSubmit}
      noValidate
      aria-describedby={Object.keys(errors).length ? `${formId}-summary` : undefined}
    >
      {Object.keys(errors).length > 0 ? (
        <div id={`${formId}-summary`} className="mm-schema-form__summary" role="alert">
          Please fix {Object.keys(errors).length} field
          {Object.keys(errors).length === 1 ? '' : 's'} before continuing.
        </div>
      ) : null}

      {Object.entries(props).map(([key, prop]) => {
        const fieldId = `${idPrefix}-${key}`;
        const helpId = `${fieldId}-help`;
        const errorId = `${fieldId}-error`;
        const label = prop.title || key;
        const t = propType(prop);
        const unit = unitOf(prop);
        const describedBy = [prop.description ? helpId : null, errors[key] ? errorId : null]
          .filter(Boolean)
          .join(' ');
        const isRequired = required.has(key);
        const raw = value[key];

        if (prop.enum && prop.enum.length > 0) {
          return (
            <div className="mm-field" key={key}>
              <label className="mm-field__label" htmlFor={fieldId}>
                {label}
                {isRequired ? <span aria-hidden="true"> *</span> : null}
              </label>
              <select
                id={fieldId}
                className="mm-input"
                value={raw === undefined || raw === null ? '' : String(raw)}
                disabled={disabled}
                required={isRequired}
                aria-invalid={Boolean(errors[key])}
                aria-describedby={describedBy || undefined}
                onChange={(e) => {
                  const v = e.target.value;
                  const sample = prop.enum![0];
                  if (typeof sample === 'number') setField(key, Number(v));
                  else if (typeof sample === 'boolean') setField(key, v === 'true');
                  else setField(key, v);
                }}
              >
                {!isRequired && !prop.default ? <option value="">Select…</option> : null}
                {prop.enum.map((opt) => (
                  <option key={String(opt)} value={String(opt)}>
                    {String(opt)}
                  </option>
                ))}
              </select>
              <FieldHelp id={helpId} text={prop.description} />
              <FieldError id={errorId} message={errors[key]} />
            </div>
          );
        }

        if (t === 'boolean') {
          return (
            <div className="mm-field mm-field--checkbox" key={key}>
              <label className="mm-field__check" htmlFor={fieldId}>
                <input
                  id={fieldId}
                  type="checkbox"
                  checked={Boolean(raw)}
                  disabled={disabled}
                  aria-invalid={Boolean(errors[key])}
                  aria-describedby={describedBy || undefined}
                  onChange={(e) => setField(key, e.target.checked)}
                />
                <span>
                  {label}
                  {isRequired ? <span aria-hidden="true"> *</span> : null}
                </span>
              </label>
              <FieldHelp id={helpId} text={prop.description} />
              <FieldError id={errorId} message={errors[key]} />
            </div>
          );
        }

        if (t === 'number' || t === 'integer') {
          const min = prop.minimum;
          const max = prop.maximum;
          return (
            <div className="mm-field" key={key}>
              <label className="mm-field__label" htmlFor={fieldId}>
                {label}
                {isRequired ? <span aria-hidden="true"> *</span> : null}
                {unit ? <span className="mm-field__unit"> ({unit})</span> : null}
              </label>
              <input
                id={fieldId}
                className="mm-input"
                type="number"
                inputMode="decimal"
                step={t === 'integer' ? 1 : (prop.multipleOf ?? 'any')}
                min={min}
                max={max}
                value={raw === undefined || raw === null ? '' : String(raw)}
                disabled={disabled}
                required={isRequired}
                aria-invalid={Boolean(errors[key])}
                aria-describedby={describedBy || undefined}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === '') setField(key, undefined);
                  else setField(key, t === 'integer' ? parseInt(v, 10) : Number(v));
                }}
              />
              {(min != null || max != null) && (
                <p className="mm-field__range" aria-hidden="true">
                  Range{min != null ? ` ${min}` : ''}
                  {max != null ? `–${max}` : '+'}
                  {unit ? ` ${unit}` : ''}
                </p>
              )}
              <FieldHelp id={helpId} text={prop.description} />
              <FieldError id={errorId} message={errors[key]} />
            </div>
          );
        }

        // default: string
        return (
          <div className="mm-field" key={key}>
            <label className="mm-field__label" htmlFor={fieldId}>
              {label}
              {isRequired ? <span aria-hidden="true"> *</span> : null}
            </label>
            <input
              id={fieldId}
              className="mm-input"
              type="text"
              value={raw === undefined || raw === null ? '' : String(raw)}
              disabled={disabled}
              required={isRequired}
              minLength={prop.minLength}
              maxLength={prop.maxLength}
              pattern={prop.pattern}
              aria-invalid={Boolean(errors[key])}
              aria-describedby={describedBy || undefined}
              onChange={(e) => setField(key, e.target.value)}
            />
            <FieldHelp id={helpId} text={prop.description} />
            <FieldError id={errorId} message={errors[key]} />
          </div>
        );
      })}

      {onSubmit ? (
        <div className="mm-schema-form__actions">
          <Button type="submit" variant="primary" disabled={disabled}>
            {submitLabel}
          </Button>
        </div>
      ) : null}
    </form>
  );
}
