import { NextRequest, NextResponse } from 'next/server';

const API_TARGET = process.env.AGENTSHIELD_API_URL ?? 'http://localhost:8000';
const OPERATOR_API_KEY = process.env.AGENTSHIELD_OPERATOR_API_KEY;
const OPERATOR_ID = process.env.AGENTSHIELD_OPERATOR_ID;

async function proxy(request: NextRequest, path: string[]) {
  const target = new URL(`/api/v1/${path.join('/')}`, API_TARGET);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  const contentType = request.headers.get('content-type');
  const requestId = request.headers.get('x-request-id');
  const correlationId = request.headers.get('x-correlation-id');
  if (contentType) headers.set('content-type', contentType);
  if (requestId) headers.set('x-request-id', requestId);
  if (correlationId) headers.set('x-correlation-id', correlationId);
  if (OPERATOR_API_KEY) headers.set('x-operator-api-key', OPERATOR_API_KEY);
  if (OPERATOR_ID) headers.set('x-operator-id', OPERATOR_ID);

  const upstream = await fetch(target, {
    method: request.method,
    headers,
    body: request.method === 'GET' || request.method === 'HEAD' ? undefined : await request.arrayBuffer(),
    cache: 'no-store',
  });

  const responseHeaders = new Headers();
  const upstreamContentType = upstream.headers.get('content-type');
  const upstreamRequestId = upstream.headers.get('x-request-id');
  if (upstreamContentType) responseHeaders.set('content-type', upstreamContentType);
  if (upstreamRequestId) responseHeaders.set('x-request-id', upstreamRequestId);

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) => context.params.then(({ path }) => proxy(request, path));
export const POST = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) => context.params.then(({ path }) => proxy(request, path));
export const PUT = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) => context.params.then(({ path }) => proxy(request, path));
export const PATCH = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) => context.params.then(({ path }) => proxy(request, path));
export const DELETE = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) => context.params.then(({ path }) => proxy(request, path));
