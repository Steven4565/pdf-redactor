<script lang="ts">
	import { FileIcon } from '@lucide/svelte';
	import { Progress, FileUpload, Dialog, Portal } from '@skeletonlabs/skeleton-svelte';
	import { goto } from '$app/navigation';
	import { documentData } from '$lib/stores/document';
	import { enhance } from '$app/forms';
	import type { ActionData } from './$types';

	const API_URL = 'http://localhost:8000/';

	let { form }: { form: ActionData } = $props();

	const categories = ['Names', 'Emails', 'Phone numbers', 'SSNs', 'Credit cards'];
	let selected: string[] = $state([]);
	let categoriesJson = $derived(JSON.stringify(selected));
	let files;

	// UI vars
	let loading = $state(false);
	let errorMsg: string | null = $state(null);

	let jobID: string | null = $state(null);
	let jobStatus = $state<'idle' | 'processing' | 'done' | 'error'>('idle');

	let pollTimeout: ReturnType<typeof setTimeout> | null = null;

	$effect(() => {
		if (form?.error) {
			errorMsg = form.error;
			loading = false;
			jobStatus = 'error';
		} else if (form?.success && form.job_id) {
			jobID = form.job_id;
			jobStatus = form.status as any;
			pollJob(form.job_id);
		}
	});

	async function pollJob(jobId: string) {
		jobStatus = 'processing';

		const checkStatus = async () => {
			try {
				const res = await fetch(`${API_URL}jobs/${jobId}`);
				if (!res.ok) throw new Error(`Status check failed (${res.status})`);

				const data = await res.json();
				const status = data.status as string;

				if (status === 'processing') {
					pollTimeout = setTimeout(checkStatus, 2000);
					return;
				}

				if (status === 'done') {
					jobStatus = 'done';
					loading = false;
					documentData.set(data.result);
					goto('/redact');
					return;
				}

				jobStatus = 'error';
				errorMsg = data.error ?? 'Job failed';
				loading = false;
			} catch (err: any) {
				jobStatus = 'error';
				errorMsg = err?.message ?? 'Failed to poll job status';
				loading = false;
			}
		};

		if (pollTimeout) {
			clearTimeout(pollTimeout);
			pollTimeout = null;
		}

		await checkStatus();
	}

	function handleSubmit() {
		errorMsg = null;
		loading = true;
		jobStatus = 'idle';
	}
</script>

<div class="grid grid-rows-[auto_1fr_auto]">
	<header class="p-4">PDF Redactor</header>
	<div class="container mx-auto grid grid-cols-1">
		<main class="col-span-1 space-y-4 p-4">
			<form
				class="space-y-2"
				method="POST"
				enctype="multipart/form-data"
				use:enhance={() => {
					handleSubmit();
					return async ({ update }) => {
						await update();
					};
				}}
			>
				<input type="hidden" name="categories" value={categoriesJson} />
				<FileUpload accept="application/pdf" maxFiles={5} preventDocumentDrop={false}>
					<FileUpload.Dropzone>
						<FileIcon class="size-10" />
						<span>Select or drag PDF files here.</span>
						<FileUpload.HiddenInput
							name="files"
							multiple
							onchange={(e) => {
								const target = e.target as HTMLInputElement;
								files = target.files;
							}}
						/>
						<FileUpload.Trigger>Browse Files</FileUpload.Trigger>
					</FileUpload.Dropzone>
					<FileUpload.ItemGroup>
						<FileUpload.Context>
							{#snippet children(fileUpload)}
								{#each fileUpload().acceptedFiles as file (file.name)}
									<FileUpload.Item {file}>
										<FileUpload.ItemName>
											{file.name}
										</FileUpload.ItemName>
										<FileUpload.ItemSizeText>
											{file.size} bytes
										</FileUpload.ItemSizeText>
										<FileUpload.ItemDeleteTrigger />
									</FileUpload.Item>
								{/each}
							{/snippet}
						</FileUpload.Context>
					</FileUpload.ItemGroup>
				</FileUpload>

				{#if errorMsg}
					<!-- TODO:  -->
					<div class="alert preset-filled-error-500">
						<p>{errorMsg}</p>
					</div>
				{/if}

				<div class="grid grid-cols-2 items-start gap-6">
					<div>
						<h5 class="pb-3 h5">Category to Redact</h5>
						<div class="space-y-2">
							{#each categories as cat}
								<label class="flex items-center space-x-2">
									<input class="checkbox" type="checkbox" value={cat} bind:group={selected} />
									<p>{cat}</p>
								</label>
							{/each}
						</div>
					</div>

					<div class="space-y-3">
						<h5 class="pb-3 h5">Process PDF</h5>
						<button type="submit" class="btn preset-filled" disabled={loading}>
							{#if loading}Processing…{/if}
							{#if !loading}Process{/if}
						</button>
					</div>
				</div>
			</form>
		</main>
	</div>
</div>
<Dialog closeOnInteractOutside={false} open={loading}>
	<Portal>
		<Dialog.Backdrop class="fixed inset-0 z-50 bg-surface-50-950/50" />
		<Dialog.Positioner class="fixed inset-0 z-50 flex items-center justify-center">
			<Dialog.Content class="w-md space-y-2 card bg-surface-100-900 p-4 shadow-xl">
				<Dialog.Title class="text-2xl font-bold">Processing File</Dialog.Title>
				<Dialog.Description>
					<Progress value={null}>
						<Progress.Track>
							<Progress.Range />
						</Progress.Track>
					</Progress>
				</Dialog.Description>
			</Dialog.Content>
		</Dialog.Positioner>
	</Portal>
</Dialog>
