'use client'
import { useRef, useState } from 'react'
import { Upload, CheckCircle, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

interface FileUploadProps {
  label: string
  accept?: string
  uploaded?: boolean
  uploading?: boolean
  error?: string
  onFileSelect: (file: File) => void
  uploadedLabel?: string
  notUploadedLabel?: string
  clickToUploadLabel?: string
}

export function FileUpload({
  label,
  accept = '.jpg,.jpeg,.png,.pdf',
  uploaded = false,
  uploading = false,
  error,
  onFileSelect,
  uploadedLabel = 'Uploaded',
  notUploadedLabel = 'Not uploaded',
  clickToUploadLabel = 'Click to upload',
}: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleFile = (file: File) => {
    onFileSelect(file)
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        {uploaded ? (
          <span className="flex items-center gap-1 text-xs text-emerald-600 font-medium">
            <CheckCircle className="h-3.5 w-3.5" />
            {uploadedLabel}
          </span>
        ) : (
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <AlertCircle className="h-3.5 w-3.5" />
            {notUploadedLabel}
          </span>
        )}
      </div>

      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          const file = e.dataTransfer.files[0]
          if (file) handleFile(file)
        }}
        className={cn(
          'border-2 border-dashed rounded-xl p-4 flex flex-col items-center gap-2',
          'cursor-pointer transition-colors',
          dragOver ? 'border-violet-400 bg-violet-50' : 'border-gray-200 hover:border-violet-300 hover:bg-violet-50/50',
          uploaded && 'border-emerald-200 bg-emerald-50/50',
          error && 'border-red-300 bg-red-50/50'
        )}
      >
        <Upload className={cn(
          'h-5 w-5',
          uploaded ? 'text-emerald-500' : 'text-gray-400'
        )} />
        <span className="text-xs text-gray-500">
          {uploading ? 'Uploading...' : clickToUploadLabel}
        </span>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
        }}
      />

      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  )
}
