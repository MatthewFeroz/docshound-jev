import { ScrollArea as Primitive } from "@base-ui/react/scroll-area";
import type { ComponentProps, ReactNode, Ref } from "react";

// shadcn's Base UI composition, styled with the app's existing CSS tokens.
export function ScrollArea({
  children,
  className = "",
  viewportRef,
  viewportProps,
}: {
  children: ReactNode;
  className?: string;
  viewportRef?: Ref<HTMLDivElement>;
  viewportProps?: ComponentProps<typeof Primitive.Viewport>;
}) {
  return (
    <Primitive.Root
      data-slot="scroll-area"
      className={`ui-scroll-area ${className}`}
    >
      <Primitive.Viewport
        ref={viewportRef}
        data-slot="scroll-area-viewport"
        className="ui-scroll-viewport"
        {...viewportProps}
      >
        <Primitive.Content className="ui-scroll-content">
          {children}
        </Primitive.Content>
      </Primitive.Viewport>
      <ScrollBar />
      <Primitive.Corner />
    </Primitive.Root>
  );
}

export function ScrollBar({
  orientation = "vertical",
}: {
  orientation?: "vertical" | "horizontal";
}) {
  return (
    <Primitive.Scrollbar
      orientation={orientation}
      data-slot="scroll-area-scrollbar"
      className="ui-scrollbar"
    >
      <Primitive.Thumb className="ui-scroll-thumb" />
    </Primitive.Scrollbar>
  );
}
