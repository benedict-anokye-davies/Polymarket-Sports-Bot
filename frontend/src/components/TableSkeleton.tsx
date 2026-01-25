import { Skeleton } from '@/components/ui/skeleton';

interface TableSkeletonProps {
  columns?: number;
  rows?: number;
}

export function TableSkeleton({ columns = 5, rows = 8 }: TableSkeletonProps) {
  return (
    <div className="w-full">
      {/* Header */}
      <div className="border-b border-border bg-muted/30 flex gap-4 py-3 px-4">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-3 flex-1" />
        ))}
      </div>
      {/* Rows */}
      <div className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, rowIdx) => (
          <div key={rowIdx} className="flex items-center gap-4 py-3 px-4">
            {Array.from({ length: columns }).map((_, colIdx) => (
              <Skeleton
                key={colIdx}
                className="h-4 flex-1"
                style={{ maxWidth: colIdx === 0 ? '200px' : '100px' }}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
