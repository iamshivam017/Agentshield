import { NextRequest, NextResponse } from 'next/server';

const API_TARGET = process.env.AGENTSHIELD_API_URL ?? 'http://localhost:8000';

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = new URL(`/health/${path.join('/')}`, API_TARGET);
  target.search = request.nextUrl.search;
  const upstream = await fetch(target, { cache: 'no-store' });
  const headers = new Headers();
  const contentType = upstream.headers.get('content-type');
  const requestId = upstream.headers.get('x-request-id');
  if (contentType) headers.set('content-type', contentType);
  if (requestId) headers.set('x-request-id', requestId);
  return new NextResponse(upstream.body, { status: upstream.status, headers });
}
