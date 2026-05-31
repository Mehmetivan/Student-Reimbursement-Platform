'use client'
import { cn, formatRiskScore, getRiskColor, getRiskBgColor } from '@/lib/utils'
import { useI18n } from '@/hooks/useI18n'
import { Card, CardHeader, CardBody } from '@/components/ui/Card'
import { CheckCircle, AlertTriangle, XCircle, Shield, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'
import type { RiskAssessment } from '@/types'

interface LayerRowProps {
  label: string
  score: number
  flags?: string[]
  details?: React.ReactNode
  expandedContent?: React.ReactNode
}

function LayerRow({ label, score, flags = [], details, expandedContent }: LayerRowProps) {
  const pct = Math.round(score * 100)
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={cn('rounded-xl border p-4', getRiskBgColor(score))}>
      <div
        className={cn('flex items-center justify-between mb-2', expandedContent && 'cursor-pointer')}
        onClick={() => expandedContent && setExpanded(!expanded)}
      >
        <span className="text-sm font-medium text-gray-800">{label}</span>
        <div className="flex items-center gap-2">
          <span className={cn('text-sm font-bold', getRiskColor(score))}>
            {formatRiskScore(score)}
          </span>
          {expandedContent && (
            expanded
              ? <ChevronUp className="h-4 w-4 text-gray-400" />
              : <ChevronDown className="h-4 w-4 text-gray-400" />
          )}
        </div>
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

      {/* Expanded detail section */}
      {expandedContent && expanded && (
        <div className="mt-3 pt-3 border-t border-white/40">
          {expandedContent}
        </div>
      )}

      {expandedContent && !expanded && (
        <p className="text-xs text-gray-400 mt-2">Click to see details</p>
      )}
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

  // Layer 1 flags and details
  const layer1Flags = []
  if (risk_factors.layer1_hash.fraud_detected) layer1Flags.push(t('duplicateDetected'))
  if (risk_factors.layer1_hash.duplicate_detected) layer1Flags.push('Self duplicate')

  const layer1Details = (
    <div className="text-xs text-gray-600 space-y-1.5">
      <p className="font-medium text-gray-700 mb-2">Hash Analysis</p>
      <div className="flex justify-between">
        <span>Duplicate by another student:</span>
        <span className={risk_factors.layer1_hash.fraud_detected ? 'text-red-600 font-medium' : 'text-emerald-600'}>
          {risk_factors.layer1_hash.fraud_detected ? 'Yes — rejected' : 'No'}
        </span>
      </div>
      <div className="flex justify-between">
        <span>Self duplicate:</span>
        <span className={risk_factors.layer1_hash.duplicate_detected ? 'text-amber-600 font-medium' : 'text-emerald-600'}>
          {risk_factors.layer1_hash.duplicate_detected ? 'Yes — already submitted' : 'No'}
        </span>
      </div>
      <div className="flex justify-between">
        <span>Weight in final score:</span>
        <span className="font-mono">{risk_factors.layer1_hash.weight} (35%)</span>
      </div>
      <p className="text-gray-400 mt-1">SHA-256 hash compared against all previous submissions globally.</p>
    </div>
  )

  // Layer 2 flags and details
  const layer2Flags = []
  if (risk_factors.layer2_exif.has_editing_software) {
    layer2Flags.push(`${t('editingSoftware')}: ${risk_factors.layer2_exif.editing_software ?? ''}`)
  }
  if (risk_factors.layer2_exif.flags?.length) {
    layer2Flags.push(...risk_factors.layer2_exif.flags)
  }

  const layer2Details = (
    <div className="text-xs text-gray-600 space-y-1.5">
      <p className="font-medium text-gray-700 mb-2">EXIF Metadata Analysis</p>
      <div className="flex justify-between">
        <span>Editing software detected:</span>
        <span className={risk_factors.layer2_exif.has_editing_software ? 'text-red-600 font-medium' : 'text-emerald-600'}>
          {risk_factors.layer2_exif.has_editing_software
            ? `Yes — ${risk_factors.layer2_exif.editing_software}`
            : 'No'}
        </span>
      </div>
      <div className="flex justify-between">
        <span>Flags detected:</span>
        <span className={layer2Flags.length > 0 ? 'text-amber-600' : 'text-emerald-600'}>
          {layer2Flags.length > 0 ? layer2Flags.join(', ').replace(/_/g, ' ') : 'None'}
        </span>
      </div>
      <div className="flex justify-between">
        <span>Weight in final score:</span>
        <span className="font-mono">{risk_factors.layer2_exif.weight} (20%)</span>
      </div>
      <p className="text-gray-400 mt-1">
        Missing EXIF suggests WhatsApp compression or image editing. Editing software in metadata confirms post-capture manipulation.
      </p>
    </div>
  )

  // Layer 3 flags and details
  const layer3Flags = risk_factors.layer3_ocr.flags ?? []

  const layer3Details = (
    <div className="text-xs text-gray-600 space-y-1.5">
      <p className="font-medium text-gray-700 mb-2">OCR — STPT Customer ID Validation</p>
      <div className="flex justify-between">
        <span>Extracted from receipt:</span>
        <span className="font-mono font-medium">
          {risk_factors.layer3_ocr.extracted_stpt_id ?? 'Not found'}
        </span>
      </div>
      <div className="flex justify-between">
        <span>Expected from profile:</span>
        <span className="font-mono font-medium">
          {risk_factors.layer3_ocr.expected_stpt_id ?? 'Not stored'}
        </span>
      </div>
      <div className="flex justify-between">
        <span>Match result:</span>
        <span className={risk_factors.layer3_ocr.stpt_id_matches ? 'text-emerald-600 font-medium' : 'text-red-600 font-medium'}>
          {risk_factors.layer3_ocr.stpt_id_matches ? 'Matched' : 'Not matched'}
        </span>
      </div>
      <div className="flex justify-between">
        <span>Flags:</span>
        <span className={layer3Flags.length > 0 ? 'text-amber-600' : 'text-emerald-600'}>
          {layer3Flags.length > 0 ? layer3Flags.join(', ').replace(/_/g, ' ') : 'None'}
        </span>
      </div>
      <div className="flex justify-between">
        <span>Weight in final score:</span>
        <span className="font-mono">{risk_factors.layer3_ocr.weight} (35%)</span>
      </div>
      <p className="text-gray-400 mt-1">
        EasyOCR and Google Cloud Vision extract the STPT ID from the receipt. A substring match handles leading zeros between card and receipt format.
      </p>
    </div>
  )

  // Layer 4 details
  const layer4Details = (
    <div className="text-xs text-gray-600 space-y-1.5">
      <p className="font-medium text-gray-700 mb-2">Receipt ID Anomaly Detection</p>
      <div className="flex justify-between">
        <span>Risk level:</span>
        <span className={cn('font-medium', getRiskColor(risk_factors.layer4_anomaly.risk))}>
          {risk_factors.layer4_anomaly.risk >= 1.0
            ? 'Exact duplicate receipt ID'
            : risk_factors.layer4_anomaly.risk >= 0.8
            ? 'Solo pattern — first receipt with this ID structure'
            : risk_factors.layer4_anomaly.risk >= 0.6
            ? 'Pair pattern — 1 similar receipt found'
            : risk_factors.layer4_anomaly.risk >= 0.4
            ? 'Triplet pattern — 2 similar receipts found'
            : 'Validated cluster — 3+ similar receipts found'}
        </span>
      </div>
      <div className="flex justify-between">
        <span>Weight in final score:</span>
        <span className="font-mono">{risk_factors.layer4_anomaly.weight} (10%)</span>
      </div>
      <p className="text-gray-400 mt-1">
        Receipt transaction IDs are compared against submissions from the last 90 days using structural pattern matching and n-gram analysis. Risk reduces retroactively as patterns are validated.
      </p>
    </div>
  )

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-violet-600" />
          <h3 className="font-semibold text-gray-900">{t('fraudAnalysis')}</h3>
        </div>
        <p className="text-xs text-gray-400 mt-0.5">Click each layer to see detailed results</p>
      </CardHeader>
      <CardBody className="flex flex-col gap-3">
        <LayerRow
          label={t('layer1')}
          score={risk_factors.layer1_hash.risk}
          flags={layer1Flags}
          expandedContent={layer1Details}
        />
        <LayerRow
          label={t('layer2')}
          score={risk_factors.layer2_exif.risk}
          flags={layer2Flags}
          expandedContent={layer2Details}
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
          expandedContent={layer3Details}
        />
        <LayerRow
          label={t('layer4')}
          score={risk_factors.layer4_anomaly.risk}
          expandedContent={layer4Details}
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
