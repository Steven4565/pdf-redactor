<script lang="ts">
	import { Tabs } from '@skeletonlabs/skeleton-svelte';
	import { ArrowRightIcon, XIcon, PlusIcon } from '@lucide/svelte';
	import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

	import { documentData, type DocumentData } from '$lib/stores/document';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';

	let documentIndex = $state(0);
	let pageIndex = $state(0);

	let inputBoxFocused = $state(false);
	let inputBoxValue = $state('');

	let canvasEl: HTMLCanvasElement;

	let localDocs = $state<DocumentData[]>([]);

	onMount(async () => {
		// No document has been sent yet
		if (!$documentData.length) goto('/');

		localDocs = structuredClone($documentData);

		const PDFJS = await import('pdfjs-dist');
		const workerSrc = await import('pdfjs-dist/build/pdf.worker.mjs?url');
		PDFJS.GlobalWorkerOptions.workerSrc = workerSrc.default;

		// TODO: load this (this is an absolute path) const fullPath =
		// get the request from python in URL form
		const loadingTask = PDFJS.getDocument($documentData[0].path);
		const pdf = await loadingTask.promise;
		const page = await pdf.getPage(1);

		const scale = 1;
		const viewport = page.getViewport({ scale });

		const context = canvasEl.getContext('2d');
		if (!context) return;

		canvasEl.height = viewport.height;
		canvasEl.width = viewport.width / 2;
		const renderContext = {
			canvasContext: context,
			viewport,
			canvas: canvasEl
		};

		await page.render(renderContext).promise;
	});

	let currentPageRedactions = $derived(
		localDocs[documentIndex]?.redactions
			.map((redaction, index) => ({ index, redaction }))
			.filter(({ redaction }) => redaction.page === pageIndex)
	);

	function deleteRedaction(redIdx: number) {
		const doc = localDocs[documentIndex];
		doc.redactions.splice(redIdx, 1);
	}

	function deleteRect(redIdx: number, rectIdx: number) {
		localDocs[documentIndex].redactions[redIdx].rects.splice(rectIdx, 1);
	}

	function addRect(redIdx: number) {
		localDocs[documentIndex].redactions[redIdx].rects.push([0, 0, 0, 0]);
	}

	function refreshPdf() {
		documentData.set(structuredClone(localDocs));
		// TODO: send to backend
	}
</script>

<div class="grid grid-rows-[auto_1fr_auto]">
	<header class="p-4">PDF Redactor</header>
	<div class="container mx-auto grid grid-cols-1">
		<main class="col-span-1 space-y-4 p-4">
			<div class="grid grid-cols-2">
				<div>
					<canvas bind:this={canvasEl} class="border shadow-sm"> </canvas>
				</div>

				<Tabs defaultValue="tab-1">
					<Tabs.List>
						<Tabs.Trigger value="tab-1">Redacted Text</Tabs.Trigger>
						<Tabs.Trigger value="tab-2">Raw Texts</Tabs.Trigger>
						<Tabs.Indicator />
					</Tabs.List>
					<Tabs.Content value="tab-1">
						<ul>
							{#each currentPageRedactions as { index, redaction }}
								<li class="flex gap-2 py-2">
									<div>
										<input class="input mb-2" type="text" value={redaction.text} />
										{#each redaction.rects as rect, rectIdx}
											<div class="mb-2 flex h-8 items-center gap-2">
												<li class="tems-center flex h-full gap-2 pl-8">
													{#each rect as r}
														<input class="input h-full w-15 text-xs" type="text" value={r} />
													{/each}
												</li>
												<button
													type="button"
													class="btn-icon h-4 w-4 preset-filled p-2"
													onclick={() => deleteRect(index, rectIdx)}
												>
													<XIcon size={15} />
												</button>
											</div>
										{/each}
									</div>
									<button
										type="button"
										class="btn-icon preset-filled"
										onclick={() => deleteRedaction(index)}
									>
										<XIcon size={25} />
									</button>
									<button
										type="button"
										class="btn-icon preset-filled"
										onclick={() => addRect(index)}
									>
										<PlusIcon size={25} />
									</button>
								</li>
							{/each}

							<li class="my-3">
								<input
									class="input mb-2"
									type="text"
									bind:value={inputBoxValue}
									placeholder="Add text to redact"
									bind:focused={inputBoxFocused}
								/>
							</li>
							{#if inputBoxFocused || inputBoxValue}
								<div class="flex gap-3">
									<button type="button" class="btn preset-filled btn-sm">
										<span>Generate Coordinates</span>
									</button>
									<button
										type="button"
										class="btn preset-filled btn-sm"
										onclick={() => {
											inputBoxValue = '';
										}}
									>
										<span>Cancel</span>
									</button>
								</div>
							{/if}
							<li class="w-full py-1"></li>
						</ul>

						<div class="flex gap-5 pt-8">
							<button type="button" class="btn preset-filled">
								<span>Refresh PDF</span>
							</button>
							<button type="button" class="btn preset-filled">
								<span>Download</span>
								<ArrowRightIcon size={18} />
							</button>
						</div>
					</Tabs.Content>
					<Tabs.Content value="tab-2">Content for Tab 2</Tabs.Content>
				</Tabs>
			</div>
		</main>
	</div>
</div>
