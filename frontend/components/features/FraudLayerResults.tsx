'use client'
import { cn, formatRiskScore, getRiskColor, getRiskBgColor } from '@/lib/utils'
import { useI18n } from '@/hooks/useI18n'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { CheckCircle, AlertTriangle, XCircle, Shield } from 'lucide-react'
import type { RiskAssessment } from '@/types'

interface LayerRowProps {
  label: string
  score: number
  flags?: string[]
  details?: React.ReactNode
}

function LayerRow({ label, score, flags = [], details }: LayerRowProps) {
  const pct = Math.round(score * 100)

  return (
    <div className={cn('rounded-xl border p-4', getRiskBgColor(score))}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-800">{label}</span>
        <span className={cn('text-sm font-bold', getRiskColor(score))}>
          {formatRiskScore(score)}
        </span>
      </div>
      {/* Progress bar */}
      <div className="w-full bg-white/60 rounded-full h-1.5 mb-2">
        <div
          className={cn(
            'h-1.5 rounded-full transition-all',
            score >= 0.7 ? 'bg-red-500' : score >= 0.4 ? 'bg-amber-500' : 'bg-emerald-500'
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      {flags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1">
          {flags.map((flag) => (
            <span key={flag} className="text-xs bg-white/70 px-2 py-0.5 rounded-full text-gray-600">
              {flag.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}
      {details}
    </div>
  )
}

interface FraudLayerResultsProps {
  assessment: RiskAssessment
}

export function FraudLayerResults({ assessment }: FraudLayerResultsProps) {
  const { t } = useI18n()
  const { risk_factors, total_risk_score } = assessment

  const FinalIcon =
    total_risk_score >= 0.7
      ? XCircle
      : total_risk_score >= 0.4
      ? AlertTriangle
      : CheckCircle

  const finalColor =
    total_risk_score >= 0.7
      ? 'text-red-600'
      : total_risk_score >= 0.4
      ? 'text-amber-500'
      : 'text-emerald-600'

  const layer1Flags = []
  if (risk_factors.layer1_hash.fraud_detected) layer1Flags.push(t('duplicateDetected'))
  if (risk_factors.layer1_hash.duplicate_detected) layer1Flags.push('Self duplicate')

  const layer2Flags = []
  if (risk_factors.layer2_exif.has_editing_software) {
    layer2Flags.push(`${t('editingSoftware')}: ${risk_factors.layer2_exif.editing_software ?? ''}`)
  }
  if (risk_factors.layer2_exif.flags?.length) {
    layer2Flags.push(...risk_factors.layer2_exif.flags)
  }

  const layer3Flags = risk_factors.layer3_ocr.flags ?? []

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-violet-600" />
          <h3 className="font-semibold text-gray-900">{t('fraudAnalysis')}</h3>
        </div>
      </CardHeader>
      <CardBody className="flex flex-col gap-3">
        <LayerRow
          label={t('layer1')}
          score={risk_factors.layer1_hash.risk}
          flags={layer1Flags}
        />
        <LayerRow
          label={t('layer2')}
          score={risk_factors.layer2_exif.risk}
          flags={layer2Flags}
        />
        <LayerRow
          label={t('layer3')}
          score={risk_factors.layer3_ocr.risk}
          flags={layer3Flags}
          details={
            risk_factors.layer3_ocr.extracted_stpt_id ? (
              <div className="mt-2 text-xs text-gray-600 space-y-0.5">
                <p>Extracted: <span className="font-mono font-medium">{risk_factors.layer3_ocr.extracted_stpt_id}</span></p>
                <p>Expected: <span className="font-mono font-medium">{risk_factors.layer3_ocr.expected_stpt_id ?? 'N/A'}</span></p>
              </div>
            ) : null
          }
        />
        <LayerRow
          label={t('layer4')}
          score={risk_factors.layer4_anomaly.risk}
        />

        {/* Final score */}
        <div className={cn('rounded-xl border-2 p-4 flex items-center justify-between', getRiskBgColor(total_risk_score))}>
          <div className="flex items-center gap-2">
            <FinalIcon className={cn('h-5 w-5', finalColor)} />
            <span className="font-semibold text-gray-900">{t('layer5')}</span>
          </div>
          <span className={cn('text-xl font-bold', finalColor)}>
            {formatRiskScore(total_risk_score)}
          </span>
        </div>
      </CardBody>
    </Card>
  )
}
