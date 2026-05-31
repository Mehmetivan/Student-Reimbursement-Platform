import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function proxy(request: NextRequest) {
  const token = request.cookies.get('token')?.value
  const { pathname } = request.nextUrl

  const publicRoutes = ['/', '/login', '/register']
  if (publicRoutes.includes(pathname)) {
  // Only auto-redirect on login, not register
    // Register should always be accessible so new users can sign up
    if (token && pathname === '/login') {
      const role = request.cookies.get('role')?.value
      return NextResponse.redirect(
        new URL(role === 'admin' ? '/admin/dashboard' : '/dashboard', request.url)
      )
    }
    return NextResponse.next()
  }

  if (!token) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  const role = request.cookies.get('role')?.value

  if (pathname.startsWith('/admin') && role !== 'admin') {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  if (
    (pathname.startsWith('/dashboard') ||
      pathname.startsWith('/profile') ||
      pathname.startsWith('/requests')) &&
    role === 'admin'
  ) {
    return NextResponse.redirect(new URL('/admin/dashboard', request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
}