/**
 * Full-page background for the login/register screens.
 *
 * Covers the entire viewport (same width behaviour as the dashboard hero - edge to
 * edge, full height, not a strip) with a translucent card holding the form centred
 * on top. Two background layers: the real photograph if one has been dropped in at
 * `public/auth-bg.jpg`, otherwise the bundled SVG - so the page is never blank while
 * waiting for the file.
 */
export function AuthBackground({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="flex min-h-screen w-full items-center justify-center bg-olive-dark px-4 py-10 [min-height:100dvh]"
      style={{
        backgroundImage: "url('/auth-bg.jpg'), url('/auth-bg.svg')",
        backgroundSize: 'cover, cover',
        backgroundPosition: 'center, center',
        backgroundRepeat: 'no-repeat, no-repeat',
      }}
    >
      <div className="w-full max-w-md rounded-2xl bg-white/95 p-6 shadow-2xl backdrop-blur-sm sm:p-8">
        {children}
      </div>
    </div>
  )
}
