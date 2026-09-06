import { cn } from '@/lib/cn'

export function TextField({
  label,
  error,
  hint,
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  label: string
  error?: string
  hint?: string
}) {
  const id = props.id ?? props.name
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        {...props}
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        className={cn(
          'block w-full rounded-lg border px-3 py-2.5 text-base',
          'focus:border-brand focus:ring-1 focus:ring-brand focus:outline-none',
          error ? 'border-red-400 bg-red-50' : 'border-slate-300',
          className,
        )}
      />
      {hint && !error && (
        <p id={`${id}-hint`} className="text-xs text-slate-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}
