import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AgentShield · Risk Command Center',
  description: 'Defense-only AI risk and trust layer for agentic payments.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
