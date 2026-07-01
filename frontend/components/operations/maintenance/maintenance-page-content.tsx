"use client";

import { CalendarClock, ClipboardList, AlertTriangle, Wrench } from "lucide-react";

import { PageHeader } from "@/components/common/page-header";
import { formatDateTime } from "@/lib/dashboard/format";
import { DataTable } from "@/components/operations/data-table";
import {
  priorityBadge,
  workOrderStatusBadge,
} from "@/components/operations/operations-badge";
import { SectionCard } from "@/components/operations/section-card";
import { StatCard } from "@/components/operations/stat-card";
import { UPCOMING_MAINTENANCE, WORK_ORDERS } from "@/lib/operations/mock-data";
import type { UpcomingMaintenance, WorkOrder } from "@/types/operations";

export function MaintenancePageContent() {
  const openCount = WORK_ORDERS.filter((wo) =>
    ["open", "in_progress", "scheduled", "overdue"].includes(wo.status),
  ).length;
  const criticalCount = WORK_ORDERS.filter((wo) => wo.priority === "critical").length;
  const overdueCount = WORK_ORDERS.filter((wo) => wo.status === "overdue").length;

  const upcomingColumns = [
    {
      key: "asset",
      header: "Asset",
      render: (row: UpcomingMaintenance) => (
        <div className="space-y-1">
          <p className="font-medium text-white">{row.assetTag}</p>
          <p className="text-xs text-muted-foreground">{row.assetName}</p>
        </div>
      ),
    },
    {
      key: "task",
      header: "Task",
      render: (row: UpcomingMaintenance) => (
        <span className="text-muted-foreground">{row.task}</span>
      ),
    },
    {
      key: "type",
      header: "Type",
      render: (row: UpcomingMaintenance) => (
        <span className="capitalize text-muted-foreground">{row.type}</span>
      ),
    },
    {
      key: "scheduled",
      header: "Scheduled",
      render: (row: UpcomingMaintenance) => (
        <span className="text-muted-foreground">{formatDateTime(row.scheduledDate)}</span>
      ),
    },
    {
      key: "assigned",
      header: "Assigned To",
      render: (row: UpcomingMaintenance) => (
        <span className="text-muted-foreground">{row.assignedTo}</span>
      ),
    },
  ];

  const workOrderColumns = [
    {
      key: "wo",
      header: "Work Order",
      render: (row: WorkOrder) => (
        <div className="space-y-1">
          <p className="font-medium text-white">{row.woNumber}</p>
          <p className="max-w-xs text-xs text-muted-foreground">{row.title}</p>
        </div>
      ),
    },
    {
      key: "asset",
      header: "Asset",
      render: (row: WorkOrder) => (
        <span className="font-mono text-xs text-[var(--accent-steel-muted)]">{row.assetTag}</span>
      ),
    },
    {
      key: "priority",
      header: "Priority",
      render: (row: WorkOrder) => priorityBadge(row.priority),
    },
    {
      key: "status",
      header: "Status",
      render: (row: WorkOrder) => workOrderStatusBadge(row.status),
    },
    {
      key: "assigned",
      header: "Assigned To",
      render: (row: WorkOrder) => (
        <span className="text-muted-foreground">{row.assignedTo}</span>
      ),
    },
    {
      key: "due",
      header: "Due Date",
      render: (row: WorkOrder) => (
        <span
          className={
            row.status === "overdue"
              ? "font-medium text-[var(--danger)]"
              : "text-muted-foreground"
          }
        >
          {row.dueDate}
        </span>
      ),
    },
    {
      key: "dept",
      header: "Department",
      render: (row: WorkOrder) => (
        <span className="text-muted-foreground">{row.department}</span>
      ),
    },
  ];

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 lg:gap-8">
      <PageHeader
        sectionLabel="Industrial Operations"
        title="Maintenance"
        description="Track upcoming preventive and corrective maintenance, open work orders, and priority assignments."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Upcoming Tasks"
          value={String(UPCOMING_MAINTENANCE.length)}
          icon={CalendarClock}
        />
        <StatCard
          label="Open Work Orders"
          value={String(openCount)}
          icon={ClipboardList}
        />
        <StatCard
          label="Critical Priority"
          value={String(criticalCount)}
          hint="Immediate action required"
          icon={AlertTriangle}
          tone="danger"
        />
        <StatCard
          label="Overdue"
          value={String(overdueCount)}
          hint="Past due date"
          icon={Wrench}
          tone="warning"
        />
      </div>

      <SectionCard
        sectionLabel="Schedule"
        title="Upcoming maintenance"
        description="Preventive, predictive, and corrective tasks scheduled across production units."
      >
        <DataTable
          columns={upcomingColumns}
          data={UPCOMING_MAINTENANCE}
          rowKey={(row) => row.id}
          minWidth="900px"
        />
      </SectionCard>

      <SectionCard
        sectionLabel="Work Management"
        title="Work orders"
        description="Active and recently completed maintenance work orders with priority and status."
      >
        <DataTable
          columns={workOrderColumns}
          data={WORK_ORDERS}
          rowKey={(row) => row.id}
          minWidth="1000px"
          footer={`${WORK_ORDERS.length} work orders on record`}
        />
      </SectionCard>
    </div>
  );
}
