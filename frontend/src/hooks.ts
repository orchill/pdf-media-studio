import { useEffect, useRef, useState } from "react";
import { getTask } from "./api";
import { TaskRecord, isTerminal } from "./types";

/** Poll a task by id until it reaches a terminal state. */
export function useTask(taskId: string | null): TaskRecord | null {
  const [task, setTask] = useState<TaskRecord | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setTask(null);
    if (!taskId) return;
    let stopped = false;
    const poll = async () => {
      try {
        const t = await getTask(taskId);
        if (stopped) return;
        setTask(t);
        if (!isTerminal(t.status)) timer.current = setTimeout(poll, 800);
      } catch {
        if (!stopped) timer.current = setTimeout(poll, 2000);
      }
    };
    poll();
    return () => {
      stopped = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [taskId]);
  return task;
}

/** Simple list reordering for drag & drop. */
export function useReorder<T>(items: T[], setItems: (v: T[]) => void) {
  const dragIndex = useRef<number | null>(null);
  return {
    onDragStart: (i: number) => () => {
      dragIndex.current = i;
    },
    onDragOver: (e: React.DragEvent) => {
      e.preventDefault();
    },
    onDrop: (i: number) => () => {
      const from = dragIndex.current;
      dragIndex.current = null;
      if (from == null || from === i) return;
      const next = [...items];
      const [moved] = next.splice(from, 1);
      next.splice(i, 0, moved);
      setItems(next);
    },
  };
}
