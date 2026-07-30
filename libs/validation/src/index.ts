import { z } from 'zod'

export const emailSchema = z.string().email().transform((e) => e.trim().toLowerCase())

export const consentSchema = z.object({
  purpose: z.string().min(1),
  channel: z.string().min(1),
  legal_basis: z.enum(['consent', 'legitimate_interest', 'contract', 'legal_obligation']).default('consent'),
  metadata: z.record(z.unknown()).default({}),
})

export const dsarSchema = z.object({
  request_type: z.enum(['access', 'deletion', 'rectification', 'export', 'portability']),
  description: z.string().max(2000).optional(),
})

export const bannerSchema = z.object({
  name: z.string().min(1).max(255),
  slug: z.string().regex(/^[a-z0-9-]+$/, 'lowercase letters, numbers, hyphens only'),
  title: z.string().max(255).optional(),
  message: z.string().max(5000).optional(),
  position: z.enum(['bottom', 'top', 'modal', 'sidebar']).default('bottom'),
  background_color: z.string().regex(/^#[0-9a-fA-F]{6}$/).default('#ffffff'),
  text_color: z.string().regex(/^#[0-9a-fA-F]{6}$/).default('#333333'),
  button_color: z.string().regex(/^#[0-9a-fA-F]{6}$/).default('#667eea'),
})
