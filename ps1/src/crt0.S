# Entry point: clear .bss, call main. The BIOS has already set sp from the EXE header.
    .set noreorder
    .section .text.start, "ax"
    .global _start
_start:
    la      $t0, __bss_start
    la      $t1, __bss_end
1:  beq     $t0, $t1, 2f
    nop
    sw      $zero, 0($t0)
    b       1b
    addiu   $t0, $t0, 4
2:  jal     main
    nop
3:  b       3b
    nop
