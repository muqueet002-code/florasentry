import { cn } from '@/lib/cn'

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-brand text-white hover:bg-brand-dark disabled:bg-slate-300',
  secondary: 'bg-white text-slate-800 border border-slate-300 hover:bg-slate-50',
  danger: 'bg-red-600 text-white hover:bg-red-700',
  ghost: 'text-slate-700 hover:bg-slate-100',
}

export function Button({
  variant = 'primary',
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      className={cn(
        // min-h-11 keeps tap targets finger-sized for outdoor phone use (PRD 16).
        'inline-flex min-h-11 items-center justify-center rounded-lg px-4 py-2 text-sm font-medium',
        'transition-colors disabled:cursor-not-allowed disabled:opacity-60',
        VARIANTS[variant],
        className,
      )}
    />
  )
}
