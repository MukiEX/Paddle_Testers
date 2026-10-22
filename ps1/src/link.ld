ENTRY(_start)
SECTIONS {
  . = 0x80010000;
  .text : { *(.text.start) *(.text*) }
  .rodata : { *(.rodata*) }
  .data : { *(.data*) *(.sdata*) }
  . = ALIGN(4);
  __bss_start = .;
  .bss (NOLOAD) : { *(.sbss*) *(.bss*) *(COMMON) }
  . = ALIGN(4);
  __bss_end = .;
  /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.comment) *(.pdr) *(.gnu.attributes) }
}
