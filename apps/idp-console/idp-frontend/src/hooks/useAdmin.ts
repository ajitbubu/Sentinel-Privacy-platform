import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { api } from '../services/api'
import type { AuditEntry, Banner, BannerVersion, DSARQueueItem, Overview } from '../types'

/* ---------- banners ---------- */
export const useBanners = (status?: string) => useQuery({
  queryKey: ['banners', status],
  queryFn: async () => (await api.get<{ banners: Banner[] }>(
    `/banner${status ? `?status=${status}` : ''}`)).data,
})

export const useBanner = (id: string | null) => useQuery({
  queryKey: ['banner', id],
  queryFn: async () => (await api.get<Banner>(`/banner/${id}`)).data,
  enabled: Boolean(id),
})

export const useBannerVersions = (id: string | null) => useQuery({
  queryKey: ['banner-versions', id],
  queryFn: async () => (await api.get<{ versions: BannerVersion[] }>(
    `/banner/${id}/versions`)).data,
  enabled: Boolean(id),
})

export function useSaveBanner(id: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: Partial<Banner> & { materially_changed?: boolean; change_note?: string }) =>
      id ? (await api.put(`/banner/${id}`, body)).data
         : (await api.post('/banner', body)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['banners'] })
      qc.invalidateQueries({ queryKey: ['banner', id] })
      qc.invalidateQueries({ queryKey: ['banner-versions', id] })
      toast.success('Banner saved')
    },
    onError: (e: { response?: { data?: { detail?: string } } }) =>
      toast.error(e.response?.data?.detail ?? 'Could not save banner'),
  })
}

export function usePublishBanner() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => (await api.post(`/banner/${id}/publish`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['banners'] })
      toast.success('Published', {
        description: 'Live in connected systems now; browsers pick it up within ~30s.',
      })
    },
    onError: (e: { response?: { data?: { detail?: string } } }) =>
      toast.error(e.response?.data?.detail ?? 'Publish failed'),
  })
}

export function useRollbackBanner(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (version: number) =>
      (await api.post(`/banner/${id}/rollback`, { target_version: version })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['banner', id] })
      qc.invalidateQueries({ queryKey: ['banner-versions', id] })
      toast.success('Rolled back')
    },
  })
}

/* ---------- DSAR ---------- */
export const useDSARQueue = (status?: string) => useQuery({
  queryKey: ['dsar-queue', status],
  queryFn: async () => (await api.get<{ requests: DSARQueueItem[]; overdue: number; due_soon: number }>(
    `/admin/dsar${status ? `?status=${status}` : ''}`)).data,
})

export function useFulfilDSAR() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, format }: { id: string; format: string }) => {
      const res = await api.post(`/admin/dsar/${id}/fulfil?format=${format}`,
        null, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `data-export-${id.slice(0, 8)}.${format}`
      a.click()
      URL.revokeObjectURL(url)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dsar-queue'] })
      toast.success('Export generated and downloaded')
    },
    onError: () => toast.error('Could not generate the export'),
  })
}

export function useDenyDSAR() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, reason }: { id: string; reason: string }) =>
      (await api.post(`/admin/dsar/${id}/deny`, { reason })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dsar-queue'] })
      toast.success('Request declined and logged')
    },
    onError: (e: { response?: { data?: { detail?: string } } }) =>
      toast.error(e.response?.data?.detail ?? 'Could not decline'),
  })
}

/* ---------- audit ---------- */
export const useAudit = (filters: Record<string, string | boolean>) => useQuery({
  queryKey: ['audit', filters],
  queryFn: async () => {
    const params = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, String(v)) })
    return (await api.get<{ entries: AuditEntry[]; total: number }>(
      `/admin/audit?${params}`)).data
  },
})

/* ---------- analytics ---------- */
export const useOverview = () => useQuery({
  queryKey: ['overview'],
  queryFn: async () => (await api.get<Overview>('/admin/analytics/overview')).data,
})
export const useTimeseries = (days = 30) => useQuery({
  queryKey: ['timeseries', days],
  queryFn: async () => (await api.get<{ series: { date: string; granted: number; withdrawn: number }[] }>(
    `/admin/analytics/timeseries?days=${days}`)).data,
})
export const useByPurpose = () => useQuery({
  queryKey: ['by-purpose'],
  queryFn: async () => (await api.get<{ purposes: { purpose: string; granted: number; withdrawn: number; grant_rate: number }[] }>(
    '/admin/analytics/by-purpose')).data,
})
